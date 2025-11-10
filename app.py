from flask import Flask, request, jsonify
import datetime
import json
import threading
import time
import os
import logging

app = Flask(__name__)

queues: dict[str, list] = {}
enqueued_users = {}
is_default_queue: dict[str,bool] = {}

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BACKUP_FILE_PATH = "/data/backup.txt"  # Path matching docker volume config
BACKUP_FILE_PATH_LOCAL = "./backup.txt"  # Fallback for local execution


# -- JOIN --
@app.route('/qjoin', methods=['POST'])
def qjoin_endpoint():
    queue_id = request.form['text']

    if queue_id == "":
        queue_id = f"#{request.form['channel_id']}"
        is_default_queue[queue_id] = True

    return qjoin(request.form['user_id'], queue_id)

def qjoin(user_id, queue_id):
    message = f"{make_tag(user_id)} is already in {get_queue_designation(queue_id)} (on position {get_queue_position_by_id(queue_id, user_id)})"
    
    if queue_id not in queues:
        queues[queue_id] = []

    if user_id not in [id for id in queues[queue_id]]:
        queues[queue_id].append(user_id)
        enqueued_users[user_id] = {'joined': datetime.datetime.now(), 'queue_id': queue_id}
        message = f"{make_tag(user_id)} has joined {get_queue_designation(queue_id)}. Position: {len(queues[queue_id])}"

    return to_static_channel_response(message + f" \n{pretty_queue(queue_id)}")

# -- LEAVE --
@app.route('/qleave', methods=['POST'])
def qleave_endpoint():
    queue_id = request.form['text']

    if queue_id == "":
        queue_id = f"#{request.form['channel_id']}"
    
    return qleave(request.form['user_id'], queue_id)

def qleave(user_id, queue_id):
    message = f"{make_tag(user_id)} is not in the *{queue_id}* queue"
    
    global queues
    if queue_id in queues and user_id in [id for id in queues[queue_id]]:
        queues[queue_id] = [id for id in queues[queue_id] if id != user_id]
        message = f"{'<@'+user_id+'>'} has left {get_queue_designation(queue_id)}. \n {pretty_queue(queue_id)}"
    
    return to_static_channel_response(message)

# -- SHOW ALL --
@app.route('/qshowall', methods=['POST'])
def show_all_endpoint():
    return to_static_channel_response(pretty_current_queues())

# -- SHOW --
@app.route('/qshow', methods=['POST'])
def show_queue_endpoint():
    queue_id = request.form['text']

    if queue_id == "":
        queue_id = f"#{request.form['channel_id']}"

    return to_static_channel_response(pretty_queue(queue_id))

# -- SWAP --
@app.route('/qswap', methods=['POST'])
def qswap_endpoint():
    if len(request.form['text'].split(' ')) < 2:
        queue_id, swap_with = f"#{request.form['channel_id']}", request.form['text']    
    elif len(request.form['text'].split(' ')) > 2:
        return to_static_channel_response("Invalid swap requested.")
    else:
        queue_id, swap_with = request.form['text'].split(' ')

    return qswap(request.form['user_id'], queue_id, swap_with)

def qswap(user_id, queue_id, swap_with):
    message = f"Invalid swap requested."

    try:
        current_pos = get_queue_position_by_id(queue_id, user_id) - 1
        swap_with_pos = int(swap_with) - 1 # crashes if invalid int

        if swap_with_pos < 0 or swap_with_pos > len(queues[queue_id]) - 1:
            return

        queues[queue_id][current_pos] = queues[queue_id][swap_with_pos]
        queues[queue_id][swap_with_pos] = user_id

        message = f"{make_tag(user_id)} swapped places with {make_tag(queues[queue_id][current_pos])}\n{pretty_queue(queue_id)}."
    finally:
        return to_static_channel_response(message)

# -- JUMP --
@app.route('/qjump', methods=['POST'])
def qjump_endpoint():
    if len(request.form['text'].split(' ')) < 1:
        return to_static_channel_response("Invalid jump request. Usage: /qjump [pos] or /qjump [queue] [pos]")
    elif len(request.form['text'].split(' ')) == 1:
        queue_id, jump_to_pos = f"#{request.form['channel_id']}", request.form['text']
    elif len(request.form['text'].split(' ')) == 2:
        queue_id, jump_to_pos = request.form['text'].split(' ')
    else:
        return to_static_channel_response("Invalid jump request. Usage: /qjump [pos] or /qjump [queue] [pos]")
    
    try:
        int_jump_to_pos = int(jump_to_pos)
        return qjump(request.form['user_id'], queue_id, int_jump_to_pos)
    except ValueError:
        return to_static_channel_response("Invalid position. Please provide a valid number.")

def qjump(user_id, queue_id, position):
    if queue_id not in queues:
        queues[queue_id] = []
    
    current_pos = get_queue_position_by_id(queue_id, user_id)
    
    max_position = len(queues[queue_id]) + 1 if current_pos is None else len(queues[queue_id])
    if position < 1 or position > max_position:
        return to_static_channel_response(f"Invalid position {position}. Please provide a position between 1 and {max_position}.")
    
    if current_pos is not None and position == current_pos:
        return to_static_channel_response(f"{make_tag(user_id)} is already at position {position} in {get_queue_designation(queue_id)}.\n{pretty_queue(queue_id)}")
    
    if current_pos is not None:
        queues[queue_id].pop(current_pos - 1)
        queues[queue_id].insert(position - 1, user_id)
        message = f"{make_tag(user_id)} jumped from position {current_pos} to position {position} in {get_queue_designation(queue_id)}.\n{pretty_queue(queue_id)}"
    else:
        # User is not in queue so just insert them at the requested position
        queues[queue_id].insert(position - 1, user_id)
        enqueued_users[user_id] = {'joined': datetime.datetime.now(), 'queue_id': queue_id}
        message = f"{make_tag(user_id)} has joined {get_queue_designation(queue_id)} at position {position}.\n{pretty_queue(queue_id)}"
    
    return to_static_channel_response(message)

# -- KICK --
@app.route('/qkick', methods=['POST'])
def qkick_endpoint():
    if len(request.form['text'].split(' ')) < 2:
        queue_id, pos_to_kick = f"#{request.form['channel_id']}", request.form['text']
        int_pos_to_kick = int(pos_to_kick)
    elif len(request.form['text'].split(' ')) > 2:
        return to_static_channel_response("Invalid kick request. Usage: /qkick [pos] or /qkick [queue] [pos]")
    else:
        queue_id, pos_to_kick = request.form['text'].split(' ')
        int_pos_to_kick = int(pos_to_kick)
        
    try:
        return qkick(queue_id, int_pos_to_kick)
    except ValueError:
        return to_static_channel_response("Kick could not be performed.")

def qkick(queue_id, position):
    if queue_id not in queues or position < 1 or position > len(queues[queue_id]):
        return to_static_channel_response(f"Invalid kick. No user at position {str(position)} in {get_queue_designation(queue_id)}.")

    kicked_user_id = queues[queue_id].pop(position - 1)

    if not any(kicked_user_id in q for q in queues.values()):
        enqueued_users.pop(kicked_user_id, None)
    
    message = f"{make_tag(kicked_user_id)} has been kicked from {get_queue_designation(queue_id)} 🥾\n{pretty_queue(queue_id)}"
    return to_static_channel_response(message)


# -- ADMIN TOOLS & COMMANDS --
@app.route('/qexportstate', methods=['POST'])
def qexportstate():
    if request.form['text'] != 'please':
        return jsonify({
            "response_type": "in_channel",
            "text": "Please do not use this slash command."
        })
    
    exportable_users = {user_id: {**data, "joined": data["joined"].isoformat()} for user_id, data in enqueued_users.items()}
    state_json = json.dumps(
        {"queues": queues, "enqueued_users": exportable_users, "is_default_queue": is_default_queue},
        separators=(',', ':')
    )
    return jsonify(response_type="in_channel", text=f"```{state_json}\n```")

@app.route('/qimportstate', methods=['POST'])
def qimportstate():
    if len(request.form['text'].split(' ', 1)) < 2 or request.form['text'].split(' ', 1)[0] != 'please':
        return jsonify({
            "response_type": "in_channel",
            "text": "Please do not use this slash command."
        })

    global queues, enqueued_users, is_default_queue
    json_blob = request.form['text'].split(' ', 1)[1]
    try:
        data = json.loads(json_blob)
        queues = data.get("queues", {})
        enqueued_users = {user_id: {**data, "joined": datetime.datetime.fromisoformat(data["joined"])} for user_id, data in data.get("enqueued_users", {}).items()}
        is_default_queue = data.get("is_default_queue", {})

        return jsonify({
            "response_type": "in_channel",
            "text": f"successfully imported state.\n{pretty_current_queues()}"
        })
    except json.JSONDecodeError:
        return jsonify(status="error", message="Invalid input state format.")

@app.route('/qinsertatposition', methods=['POST'])
def qinsertatposition_endpoint():
    command_text = request.form['text'].split(' ')
    
    if len(command_text) < 2 or len(command_text) > 3:
        return to_static_channel_response("Invalid command format. Usage: /qinsertatposition [queue-name] [user-id] [position] or /qinsertatposition [user-id] [position]")

    # If queue id is provided
    if len(command_text) == 3:
        queue_id = command_text[0]
        user_id_to_insert = command_text[1]
        try:
            position_to_insert = int(command_text[2])
        except ValueError:
            return to_static_channel_response("Invalid position provided. Please provide a valid integer for the position.")
    else:
        queue_id = f"#{request.form['channel_id']}"
        user_id_to_insert = command_text[0]
        try:
            position_to_insert = int(command_text[1])
        except ValueError:
            return to_static_channel_response("Invalid position provided. Please provide a valid integer for the position.")
    
    return qinsertatposition(user_id_to_insert, queue_id, position_to_insert)

def qinsertatposition(user_id_to_insert, queue_id, position_to_insert):
    if queue_id not in queues:
        return to_static_channel_response(f"Queue {queue_id} does not exist.")
    if position_to_insert < 1 or position_to_insert > len(queues[queue_id]) + 1:
        return to_static_channel_response(f"Invalid position {position_to_insert}. Please provide a position between 1 and {len(queues[queue_id]) + 1}.")
    
    queues[queue_id].insert(position_to_insert - 1, user_id_to_insert)
    enqueued_users[user_id_to_insert] = {'joined': datetime.datetime.now(), 'queue_id': queue_id}
    
    message = f"{make_tag(user_id_to_insert)} has been inserted at position {position_to_insert} in {get_queue_designation(queue_id)}.\n{pretty_queue(queue_id)}"
    
    return to_static_channel_response(message)


# -- PERSISTENT STATE BACKUP/RESTORE --
def save_state_to_backup():
    try:
        backup_path = get_backup_file_path()
        
        # Ensure directory exists
        os.makedirs(os.path.dirname(backup_path), exist_ok=True)
        
        exportable_users = {user_id: {**data, "joined": data["joined"].isoformat()} for user_id, data in enqueued_users.items()}
        
        state_data = {
            "queues": queues,
            "enqueued_users": exportable_users,
            "is_default_queue": is_default_queue,
            "backup_timestamp": datetime.datetime.now().isoformat()
        }
        
        with open(backup_path, 'w') as f:
            json.dump(state_data, f, separators=(',', ':'))
        
        logger.info(f"State backed up successfully to {backup_path}")
        
    except Exception as e:
        logger.error(f"Failed to save backup - error: {e}")

def restore_state_from_backup():
    global queues, enqueued_users, is_default_queue
    
    try:
        backup_path = get_backup_file_path()
        
        if not os.path.exists(backup_path):
            logger.info(f"No state file found at {backup_path}, starting with empty state")
            return
        
        with open(backup_path, 'r') as f:
            data = json.load(f)
        
        # Restore state
        queues = data.get("queues", {})
        enqueued_users = {user_id: {**user_data, "joined": datetime.datetime.fromisoformat(user_data["joined"])} for user_id, user_data in data.get("enqueued_users", {}).items()}
        is_default_queue = data.get("is_default_queue", {})
        
        backup_timestamp = data.get("backup_timestamp", "unknown")
        logger.info(f"State restored successfully from backup created at {backup_timestamp}")
    except Exception as e:
        logger.error(f"Failed to restore from backup: {e}")
        logger.info("Starting with empty state")

def backup_worker():
    while True:
        # Backup state every 1 hour
        time.sleep(3600)
        save_state_to_backup()


# -- UTIL METHODS --
def pretty_current_queues():
    result = ""
    for k,l in queues.items():
        if l != []:
            result += f"*Queue {k}:*\n{currentQueuePositions(k)}\n"
    
    if result == "":
        return "There are no active queues."
    return result

def pretty_queue(queue_id):
    if queue_id in queues and len(queues[queue_id]) > 0:
        return f"{'*This channels queue:*' if queue_id in is_default_queue else 'Current *'+queue_id+'* queue:'}\n{currentQueuePositions(queue_id)}"
    return f"{'The current queue is empty.' if queue_id in is_default_queue else 'The queue *'+queue_id+'* is empty.'}"

def currentQueuePositions(queue_id):
    return "\n".join([f"{index+1}. {make_tag(id)} - Joined at {simplify_timestamp(enqueued_users[id]['joined'])}" for index, id in enumerate(queues[queue_id])])

def get_queue_position_by_id(queue_id, user_id):
    if queue_id not in queues:
        return None

    for position, enqueued_id in enumerate(queues[queue_id]):
        if enqueued_id == user_id:
            return position+1
    return None

def make_tag(id):
    return '<@'+id+'>'

def simplify_timestamp(timestamp):
    return timestamp.strftime("%H:%M UTC, on %b %d")

def get_queue_designation(queue_id):
    if queue_id in is_default_queue:
        return "this channel\'s queue"
    else:
        return f"the *{queue_id}* queue"

def fallback_if_blank(input, fallback):
    result = input
    if result == "":
        return fallback
    return result

def to_static_channel_response(message: str):
    return jsonify({
            "response_type": "in_channel",
            "text": f"{message}\n_Commands:_ `/qshow`, `/qjoin`, `/qleave`, `/qswap [pos]`, `/qjump [pos]` _and_ `/qkick [pos]`"
        })

def get_backup_file_path():
    # Check if /data directory exists (docker volume mount)
    if os.path.exists("/data"):
        return BACKUP_FILE_PATH
    else:
        return BACKUP_FILE_PATH_LOCAL

def start_periodic_backup_thread():
    backup_thread = threading.Thread(target=backup_worker, daemon=True)
    backup_thread.start()


if __name__ == '__main__':
    restore_state_from_backup()
    start_periodic_backup_thread()
    save_state_to_backup()
    app.run(host='0.0.0.0', port=8080)
