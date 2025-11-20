# --- Imports ---
import grpc
import service_pb2
import service_pb2_grpc

from flask import request, jsonify
from flask_socketio import SocketIO, emit, disconnect
from models import app, db, bcrypt, User, Message, Friendship 
from sqlalchemy import or_ 
from flask_jwt_extended import (
    create_access_token, 
    JWTManager, 
    jwt_required, 
    get_jwt_identity
)
from flask_jwt_extended.utils import decode_token
from jwt.exceptions import PyJWTError

# --- Config ---
jwt = JWTManager(app)
app.config["JWT_TOKEN_LOCATION"] = ["headers"]
app.config["JWT_HEADER_NAME"] = "Authorization"
app.config["JWT_HEADER_TYPE"] = "Bearer"

socketio = SocketIO(app, cors_allowed_origins="*")

# --- Global State (Online Users) ---
user_to_sid = {} 
sid_to_user = {} 

# --- Helper Functions ---
def user_to_json(u):
    return {
        'id': u.id, 
        'username': u.username, 
        'display_name': u.display_name,
        'avatar': u.avatar_base64
    }

# --- API: Authentication ---

@app.route('/register', methods=['POST'])
def register():
    data = request.get_json()
    required = ['username', 'password', 'email', 'display_name']
    if not all(k in data for k in required):
        return jsonify({'error': 'Missing required fields'}), 400
    
    if User.query.filter_by(username=data['username']).first():
        return jsonify({'error': 'Username already exists'}), 409
    if User.query.filter_by(email=data['email']).first():
        return jsonify({'error': 'Email already exists'}), 409

    hashed_pw = bcrypt.generate_password_hash(data['password']).decode('utf-8')
    
    new_user = User(
        username=data['username'], 
        password_hash=hashed_pw,
        email=data['email'],
        display_name=data['display_name'],
        gender=data.get('gender'),
        dob=data.get('dob'),
        avatar_base64=data.get('avatar')
    )
    
    try:
        db.session.add(new_user)
        db.session.commit()
        return jsonify({'message': 'User created successfully'}), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Database error: {str(e)}'}), 500

@app.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    user = User.query.filter_by(username=data['username']).first()

    if not user or not bcrypt.check_password_hash(user.password_hash, data['password']):
        return jsonify({'error': 'Invalid credentials'}), 401

    access_token = create_access_token(identity=str(user.id))
    
    return jsonify({
        'message': 'Login successful',
        'access_token': access_token,
        'user_id': user.id,
        'username': user.username,
        'display_name': user.display_name,
        'avatar': user.avatar_base64
    }), 200

# --- API: Social Features ---

@app.route('/search_users', methods=['GET'])
@jwt_required()
def search_users():
    query = request.args.get('q', '')
    current_user_id = int(get_jwt_identity())
    if not query: return jsonify([]), 200

    users = User.query.filter(
        or_(User.username.contains(query), User.display_name.contains(query)),
        User.id != current_user_id
    ).all()

    results = []
    for u in users:
        friendship = Friendship.query.filter(
            ((Friendship.sender_id == current_user_id) & (Friendship.receiver_id == u.id)) |
            ((Friendship.sender_id == u.id) & (Friendship.receiver_id == current_user_id))
        ).first()
        
        status = 'none'
        if friendship:
            status = friendship.status
            if status == 'pending' and friendship.receiver_id == current_user_id:
                status = 'incoming_request' 

        u_data = user_to_json(u)
        u_data['status'] = status
        results.append(u_data)
    
    return jsonify(results), 200

@app.route('/friend_request', methods=['POST'])
@jwt_required()
def send_friend_request():
    data = request.get_json()
    sender_id = int(get_jwt_identity())
    receiver_id = data.get('receiver_id')

    if not receiver_id or sender_id == receiver_id: return jsonify({'error': 'Invalid Request'}), 400

    existing = Friendship.query.filter(
        ((Friendship.sender_id == sender_id) & (Friendship.receiver_id == receiver_id)) |
        ((Friendship.sender_id == receiver_id) & (Friendship.receiver_id == sender_id))
    ).first()

    if existing: return jsonify({'error': 'Relationship exists'}), 400

    new_friendship = Friendship(sender_id=sender_id, receiver_id=receiver_id, status='pending')
    db.session.add(new_friendship)
    db.session.commit()

    receiver_sid = user_to_sid.get(receiver_id)
    if receiver_sid:
        socketio.emit('new_friend_request', {'from_user': sender_id}, room=receiver_sid)

    return jsonify({'message': 'Request sent'}), 201

@app.route('/friend_response', methods=['POST'])
@jwt_required()
def respond_friend_request():
    data = request.get_json()
    user_id = int(get_jwt_identity())
    sender_id = data.get('sender_id')
    action = data.get('action')

    friendship = Friendship.query.filter_by(sender_id=sender_id, receiver_id=user_id, status='pending').first()
    if not friendship: return jsonify({'error': 'Not found'}), 404

    if action == 'accept':
        friendship.status = 'accepted'
        db.session.commit()
        return jsonify({'message': 'Accepted'}), 200
    elif action == 'reject':
        db.session.delete(friendship)
        db.session.commit()
        return jsonify({'message': 'Rejected'}), 200
    
    return jsonify({'error': 'Invalid action'}), 400

@app.route('/friends', methods=['GET'])
@jwt_required()
def get_friends():
    user_id = int(get_jwt_identity())
    friendships = Friendship.query.filter(
        ((Friendship.sender_id == user_id) | (Friendship.receiver_id == user_id)) &
        (Friendship.status == 'accepted')
    ).all()

    friend_list = []
    for f in friendships:
        fid = f.receiver_id if f.sender_id == user_id else f.sender_id
        fuser = db.session.get(User, fid)
        if fuser: 
            friend_list.append(user_to_json(fuser))
            
    return jsonify(friend_list), 200

@app.route('/pending_requests', methods=['GET'])
@jwt_required()
def get_pending_requests():
    user_id = int(get_jwt_identity())
    reqs = Friendship.query.filter_by(receiver_id=user_id, status='pending').all()
    result = []
    for r in reqs:
        s = db.session.get(User, r.sender_id)
        if s: result.append(user_to_json(s))
    return jsonify(result), 200

# --- API: Chat History ---

@app.route('/chat_history/<int:other_user_id>', methods=['GET'])
@jwt_required()
def get_chat_history(other_user_id):
    current_user_id = int(get_jwt_identity())
    messages = Message.query.filter(
        ((Message.sender_id == current_user_id) & (Message.receiver_id == other_user_id)) |
        ((Message.sender_id == other_user_id) & (Message.receiver_id == current_user_id))
    ).order_by(Message.timestamp.asc()).all()
    
    message_list = [
        {'id': m.id, 'sender_id': m.sender_id, 'receiver_id': m.receiver_id, 'content': m.content, 'timestamp': m.timestamp.isoformat()} 
        for m in messages
    ]
    return jsonify(message_list), 200

# --- WebSocket Events ---

@socketio.on('connect')
def handle_connect(auth): 
    print(f"Client connecting: {request.sid}")
    token = auth.get('token')
    if not token:
        disconnect()
        return

    try:
        payload = decode_token(token)
        user_id = int(payload['sub'])
        user = db.session.get(User, user_id)
        if not user: raise Exception("User not found")
    except Exception as e:
        print(f"Auth Fail: {e}")
        disconnect()
        return

    # gRPC Validation
    try:
        with grpc.insecure_channel('localhost:50051') as channel:
            stub = service_pb2_grpc.UserValidationStub(channel)
            req = service_pb2.UserRequest(user_id=user.id, username=user.username)
            resp = stub.CheckUserStatus(req, timeout=2.0)
            if resp.is_banned:
                emit('error', {'message': resp.message})
                disconnect()
                return
    except: pass 

    user_to_sid[user_id] = request.sid
    sid_to_user[request.sid] = user_id
    print(f"User {user.id} connected")

@socketio.on('disconnect')
def handle_disconnect():
    sid = request.sid
    user_id = sid_to_user.get(sid)
    if user_id:
        if user_to_sid.get(user_id) == sid:
            del user_to_sid[user_id]
        del sid_to_user[sid]

@socketio.on('send_message')
def handle_send_message(data):
    sender_sid = request.sid
    sender_id = sid_to_user.get(sender_sid)
    if not sender_id: return

    receiver_id = data.get('to_user_id')
    content = data.get('content')
    
    try:
        new_msg = Message(sender_id=sender_id, receiver_id=receiver_id, content=content)
        db.session.add(new_msg)
        db.session.commit()
    except:
        db.session.rollback()
        return

    payload = {
        'id': new_msg.id, 'sender_id': sender_id, 'receiver_id': receiver_id, 
        'content': content, 'timestamp': new_msg.timestamp.isoformat()
    }

    receiver_sid = user_to_sid.get(receiver_id)
    if receiver_sid:
        socketio.emit('new_message', payload, room=receiver_sid)
    emit('new_message', payload)

# --- Main Execution ---
if __name__ == '__main__':
    print("Server running on http://127.0.0.1:8000")
    socketio.run(app, host='127.0.0.1', port=8000, debug=True, allow_unsafe_werkzeug=True)