from flask import Flask, request, jsonify

app = Flask(__name__)

queue = []

@app.route('/qjoin', methods=['POST'])
def qjoin():
    print(request.form['response_url'])

    user_id = request.form['user_id']
    
    if user_id not in queue:
        queue.append(user_id)

    queue_list = "\n".join([f"{idx+1}. {'<@'+uid+'>'}" for idx, uid in enumerate(queue)])

    return jsonify({
        "response_type": "in_channel",
        "text": f"{'<@'+user_id+'>'} has joined the queue. Position: {len(queue)}\n{queue_list}"
    })

@app.route('/qleave', methods=['POST'])
def qleave():
    user_id = request.form['user_id']
    
    global queue
    queue = [uid for uid in queue if uid != user_id]

    queue_list = "\n".join([f"{idx+1}. {'<@'+uid+'>'}" for idx, uid in enumerate(queue)])
    
    return jsonify({
        "response_type": "in_channel",
        "text": f"{'<@'+user_id+'>'} has left the queue. \n{queue_list}"
    })

@app.route('/qshow', methods=['POST'])
def show_queue():
    if not queue:
        return jsonify({
            "response_type": "in_channel",
            "text": "The queue is empty."
        })
    
    queue_list = "\n".join([f"{idx+1}. {'<@'+uid+'>'}" for idx, uid in enumerate(queue)])

    return jsonify({
        "response_type": "in_channel",
        "text": f"Current queue:\n{queue_list}"
    })

if __name__ == '__main__':
    app.run(port=8080)

