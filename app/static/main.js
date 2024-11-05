from flask import Flask, jsonify

app = Flask(__name__)

@app.route('/api/status')
def status():
    return jsonify({"message": "API is working"})  # Basic test response

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=2000)
