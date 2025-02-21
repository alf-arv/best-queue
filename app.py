from flask import Flask, request, jsonify
import datetime
import json

app = Flask(__name__)

queues: dict[str, list] = {}
enqueued_users = {}
is_default_queue: dict[str,bool] = {}

@app.route('/qjoin', methods=['POST'])
def qjoin_endpoint():
    queue_id = request.form['text']

    if queue_id == "":
        queue_id = f"#{request.form['channel_id']}"
        is_default_queue[queue_id] = True

    return qjoin(request.form['user_id'], request.form['user_name'], queue_id)

def qjoin(user_id, user_name, queue_id):
    message = f"{make_tag(user_id)} is already in {get_queue_designation(queue_id)} (on position {get_queue_position_by_id(queue_id, user_id)})"
    
    if queue_id not in queues:
        queues[queue_id] = []

    if user_id not in [id for id in queues[queue_id]]:
        queues[queue_id].append(user_id)
        enqueued_users[user_id] = {'joined': datetime.datetime.now(), 'name': user_name, 'queue_id': queue_id}
        message = f"{make_tag(user_id)} has joined {get_queue_designation(queue_id)}. Position: {len(queues[queue_id])}"

    return to_potentially_interactive_channel_response(message + f" \n{pretty_queue(queue_id)}", queue_id)

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
    
    return to_potentially_interactive_channel_response(message, queue_id)

@app.route('/qshowall', methods=['POST'])
def show_all_endpoint():
    return to_static_channel_response(pretty_current_queues())

@app.route('/qshow', methods=['POST'])
def show_queue_endpoint():
    queue_id = request.form['text']

    if queue_id == "":
        queue_id = f"#{request.form['channel_id']}"

    return to_static_channel_response(pretty_queue(queue_id))

@app.route('/qcreate', methods=['POST'])
def create_new_queue_if_not_exists_endpoint():
    queue_id = request.form['text']
    return create_new_queue_if_not_exists(queue_id)

def create_new_queue_if_not_exists(new_queue_id):
    message = f"Unable to create the queue with name *{new_queue_id}*."
    if queues[new_queue_id]:
        message = f"Queue *{new_queue_id}* already exists."
    else:
        queues[new_queue_id] = []
        message = f"Queue *{new_queue_id}* created."
    return to_static_channel_response(message)

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

@app.route('/buttonproxy', methods=['POST'])
def route_to_action():
    # using the action buttons, all values below are available
    payload = json.loads(request.form['payload'])
    action = payload['actions'][0]['name']
    user_id = payload['user']['id']
    channel_id = "#"+payload['channel']['id']

    if action == "qjoin":
        user_name = payload['user']['name']
        return qjoin(user_id, user_name, channel_id)
    if action == "qleave":
        return qleave(user_id, channel_id)

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
        return f"{'This channels queue:' if queue_id in is_default_queue else 'Current *'+queue_id+'* queue:'}\n{currentQueuePositions(queue_id)}"
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
    return str(timestamp.time().hour)+':'+str(timestamp.time().minute)

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

def to_potentially_interactive_channel_response(message: str, queue_id: str):
    if queue_id in is_default_queue:
        return to_interactive_channel_response(message)
    else:
        return to_static_channel_response(message)

def to_interactive_channel_response(message: str):
    return jsonify({
            "response_type": "in_channel",
            "text": f"{message}",
            "attachments": [
            {
                "text": "Actions:",
                "fallback": "You are unable to manage the queue",
                "callback_id": "queue_actions",
                "color": "#3AA3E3",
                "attachment_type": "default",
                "actions": [
                    {
                        "name": "qjoin",
                        "text": "Join",
                        "type": "button",
                        "value": "join"
                    },
                    {
                        "name": "qleave",
                        "text": "Leave",
                        "type": "button",
                        "value": "leave"
                    }
                ]
            }
        ]
        })

def to_static_channel_response(message: str):
    return jsonify({
            "response_type": "in_channel",
            "text": f"{message}"
        })


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)
