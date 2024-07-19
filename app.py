from flask import Flask, request, jsonify
import datetime
import json

app = Flask(__name__)

queues: dict[str, list] = {}
enqueued_users = {}

@app.route('/qjoin', methods=['POST'])
def qjoin_endpoint():
    queue_name = request.form['text']

    if queue_name == "":
        queue_name = f"#{request.form['channel_name']}"

    return qjoin(request.form['user_id'], queue_name)

def qjoin(user_id, queue_name):
    message = f"{make_tag(user_id)} is already in the *{queue_name}* queue (on position {get_queue_position_by_id(queue_name, user_id)})"
    
    if queue_name not in queues:
        queues[queue_name] = []

    if user_id not in [id for id in queues[queue_name]]:
        queues[queue_name].append(user_id)
        enqueued_users[user_id] = {'joined': datetime.datetime.now(), 'queue_name': queue_name}
        message = f"{make_tag(user_id)} has joined the *{queue_name}* queue. Position: {len(queues[queue_name])}"

    return to_channel_response(message + f" \n{pretty_queue(queue_name)}")

@app.route('/qleave', methods=['POST'])
def qleave_endpoint():
    queue_name = request.form['text']

    if queue_name == "":
        queue_name = f"#{request.form['channel_name']}"
    
    return qleave(request.form['user_id'], queue_name)

def qleave(user_id, queue_name):
    message = f"{make_tag(user_id)} is not in the *{queue_name}* queue"
    
    global queues
    if user_id in [id for id in queues[queue_name]]:
        queues[queue_name] = [id for id in queues[queue_name] if id != user_id]
        message = f"{'<@'+user_id+'>'} has left the *{queue_name}* queue. \n {pretty_queue(queue_name)}"
    
    return to_channel_response(message)

@app.route('/qshowall', methods=['POST'])
def show_all_endpoint():
    return to_channel_response(pretty_current_queues())

@app.route('/qshow', methods=['POST'])
def show_queue_endpoint():
    queue_name = request.form['text']

    if queue_name == "":
        queue_name = f"#{request.form['channel_name']}"

    return to_channel_response(pretty_queue(queue_name))

@app.route('/qcreate', methods=['POST'])
def create_new_queue_if_not_exists_endpoint():
    queue_name = request.form['text']
    return create_new_queue_if_not_exists(queue_name)

def create_new_queue_if_not_exists(new_queue_name):
    message = f"Unable to create the queue with name *{new_queue_name}*."
    if queues[new_queue_name]:
        message = f"Queue *{new_queue_name}* already exists."
    else:
        queues[new_queue_name] = []
        message = f"Queue *{new_queue_name}* created."
    return to_channel_response(message)

@app.route('/qswap', methods=['POST'])
def qswap_endpoint():
    if len(request.form['text'].split(' ')) < 2:
        queue_name, swap_with = f"#{request.form['channel_name']}", request.form['text']    
    else:
        queue_name, swap_with = request.form['text'].split(' ')

    return qswap(request.form['user_id'], queue_name, swap_with)

def qswap(user_id, queue_name, swap_with):
    message = f"Invalid swap requested."

    try:
        current_pos = get_queue_position_by_id(queue_name, user_id)-1
        swap_with_pos = int(swap_with) - 1 # crashes if invalid int

        queues[queue_name][current_pos] = queues[queue_name][swap_with_pos]
        queues[queue_name][swap_with_pos] = user_id

        message = f"{make_tag(user_id)} swapped places with {make_tag(queues[queue_name][current_pos])}\n{pretty_queue(queue_name)}."
    finally:
        return to_channel_response(message)

@app.route('/buttonproxy', methods=['POST'])
def route_to_action():
    # using the action buttons, all values below are available
    payload = json.loads(request.form['payload'])
    action = payload['actions'][0]['name']
    user_id = payload['user']['id']
    channel_name = "#"+payload['channel']['name']

    if action == "qjoin":
        return qjoin(user_id, channel_name)
    if action == "qleave":
        return qleave(user_id, channel_name)

def pretty_current_queues():
    result = ""

    for k,l in queues.items():
        result += f"*Queue {k}:*\n{currentQueuePositions(k)}\n"
    
    if result == "":
        return "There are no active queues."
    return result

def pretty_queue(queue_name):
    if queue_name in queues and len(queues[queue_name]) > 0:
        return f"Current *{queue_name}* queue:\n{currentQueuePositions(queue_name)}"
    return f"The queue *{queue_name}* is empty."

def currentQueuePositions(queue_name):
    return "\n".join([f"{index+1}. {make_tag(id)} - Joined at {simplify_timestamp(enqueued_users[id]['joined'])}" for index, id in enumerate(queues[queue_name])])

def get_queue_position_by_id(queue_name, user_id):
    if queue_name not in queues:
        return None

    for position, enqueued_id in enumerate(queues[queue_name]):
        if enqueued_id == user_id:
            return position+1
    return None

def make_tag(id):
    return '<@'+id+'>'

def simplify_timestamp(timestamp):
    return str(timestamp.time().hour)+':'+str(timestamp.time().minute)

def fallback_if_blank(input, fallback):
    result = input
    if result == "":
        return fallback
    return result

def to_channel_response(message):
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

if __name__ == '__main__':
    app.run(port=8080, debug=True)
