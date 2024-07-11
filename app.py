from flask import Flask, request, jsonify
import datetime

app = Flask(__name__)

queue = []
enqueued_users = {}

@app.route('/qjoin', methods=['POST'])
def qjoin():
    user_id = request.form['user_id']
    message = f"{make_tag(user_id)} is already in the queue (on position {get_queue_position_by_id(user_id)})"
    
    if user_id not in [id for id in queue]:
        queue.append(user_id)
        enqueued_users[user_id] = {'joined': datetime.datetime.now()}
        message = f"{make_tag(user_id)} has joined the queue. Position: {len(queue)}"

    return to_channel_response(message + f" \n{prettyCurrentQueue()}")

@app.route('/qleave', methods=['POST'])
def qleave():
    user_id = request.form['user_id']
    message = f"{make_tag(user_id)} is not in the queue"
    
    global queue
    if user_id in [id for id in queue]:
        queue = [id for id in queue if id != user_id]
        message = f"{'<@'+user_id+'>'} has left the queue. \n {prettyCurrentQueue()}"
    
    return to_channel_response(message)

@app.route('/qshow', methods=['POST'])
def show_queue():
    return to_channel_response(prettyCurrentQueue())

@app.route('/qswap', methods=['POST'])
def qswap():
    user_id = request.form['user_id']
    message = f"Invalid swap requested."

    try:
        current_pos = get_queue_position_by_id(user_id)-1
        swap_with_pos = int(request.form['text']) - 1 # crashes if invalid int

        queue[current_pos] = queue[swap_with_pos]
        queue[swap_with_pos] = user_id

        message = f"{user_id} swapped places with {queue[current_pos]}\n{prettyCurrentQueue()}."
    finally:
        return to_channel_response(message)

def prettyCurrentQueue():
    if len(queue) > 0:
        return f"Current queue:\n{currentQueuePositions()}"
    return "The queue is empty."

def currentQueuePositions():
    return "\n".join([f"{index+1}. {make_tag(id)} - Joined at {simplify_timestamp(enqueued_users[id]['joined'])}" for index, id in enumerate(queue)])

def get_queue_position_by_id(user_id):
    for position, enqueued_id in enumerate(queue):
        if enqueued_id == user_id:
            return position+1
    return None

def make_tag(id):
    return '<@'+id+'>'

def simplify_timestamp(timestamp):
    return str(timestamp.time().minute)+':'+str(timestamp.time().hour)

def to_channel_response(message):
    return jsonify({
            "response_type": "in_channel",
            "text": f"{message}"
        })

if __name__ == '__main__':
    app.run(port=8080, debug=True)
