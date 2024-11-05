from flask import Blueprint, jsonify, request
from .collexions_api import load_config, update_config, get_logs

api = Blueprint('api', __name__)

@api.route('/status', methods=['GET'])
def status():
    return jsonify({
        "config": load_config(),
        "logs": get_logs()
    })

@api.route('/update-config', methods=['POST'])
def config():
    new_config = request.json
    update_config(new_config)
    return jsonify({"message": "Configuration updated successfully."})

@api.route('/pin-now', methods=['POST'])
def pin_now():
    # Load the current config and set the trigger flag
    config = load_config()
    config["trigger_pin"] = True
    update_config(config)
    return jsonify({"message": "Pinning action triggered."})
