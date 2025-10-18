from flask import Flask, request, jsonify, send_from_directory, make_response
from flask_cors import CORS
import json
import os
import uuid
import hashlib
import time
from datetime import datetime, timedelta
import threading
import base64
import requests

app = Flask(__name__)
CORS(app, supports_credentials=True)
app.config['SECRET_KEY'] = 'your-secret-key-here'  # 用于加密会话

# 配置
CONFIG = {
    'host': '0.0.0.0',
    'port': 9074,
    'data_dir': 'chat_data',
    'servers_file': 'servers.json',
    'users_file': 'users.json',
    'friends_file': 'friends.json',
    'uploads_dir': 'uploads',
    'ollama_url': 'http://localhost:11434'
}

# 确保数据目录存在
for dir_name in [CONFIG['data_dir'], CONFIG['uploads_dir']]:
    if not os.path.exists(dir_name):
        os.makedirs(dir_name)

# 服务器管理
class ServerManager:
    def __init__(self):
        self.servers_file = os.path.join(CONFIG['data_dir'], CONFIG['servers_file'])
        self.load_servers()
    
    def load_servers(self):
        if os.path.exists(self.servers_file):
            with open(self.servers_file, 'r') as f:
                self.servers = json.load(f)
        else:
            self.servers = {}
    
    def save_servers(self):
        with open(self.servers_file, 'w') as f:
            json.dump(self.servers, f, indent=2)
    
    def create_server(self, server_id, server_name, creator, password=None, description=""):
        server_data = {
            'id': server_id,
            'name': server_name,
            'creator': creator,
            'description': description,
            'password': password,
            'is_encrypted': password is not None,
            'created_at': datetime.now().isoformat(),
            'users': {},
            'channels': {
                'general': {
                    'name': 'General',
                    'type': 'public'
                }
            },
            'private_chats': {}
        }
        
        # 创建服务器目录
        server_dir = os.path.join(CONFIG['data_dir'], server_id)
        if not os.path.exists(server_dir):
            os.makedirs(server_dir)
        
        # 初始化消息文件
        messages_file = os.path.join(server_dir, 'messages.jsonl')
        if not os.path.exists(messages_file):
            with open(messages_file, 'w') as f:
                pass
        
        self.servers[server_id] = server_data
        self.save_servers()
        return server_data
    
    def get_server(self, server_id):
        return self.servers.get(server_id)
    
    def get_all_servers(self):
        return self.servers
    
    def verify_server_password(self, server_id, password):
        server = self.get_server(server_id)
        if not server:
            return False
        return server.get('password') == password

# 用户管理
class UserManager:
    def __init__(self):
        self.users_file = os.path.join(CONFIG['data_dir'], CONFIG['users_file'])
        self.load_users()
        self.online_users = {}  # {user_id: last_seen}
        self.sessions = {}  # {session_id: {user_data, expiry}}
    
    def load_users(self):
        if os.path.exists(self.users_file):
            with open(self.users_file, 'r') as f:
                self.users = json.load(f)
        else:
            self.users = {}
    
    def save_users(self):
        with open(self.users_file, 'w') as f:
            json.dump(self.users, f, indent=2)
    
    def create_session(self, user_data):
        """创建会话并返回session_id"""
        session_id = str(uuid.uuid4())
        expiry = datetime.now() + timedelta(days=7)
        self.sessions[session_id] = {
            'user_data': user_data,
            'expiry': expiry
        }
        return session_id
    
    def get_user_by_session(self, session_id):
        """根据session_id获取用户信息"""
        if session_id in self.sessions:
            session = self.sessions[session_id]
            # 检查会话是否过期
            if datetime.now() < session['expiry']:
                return session['user_data']
            else:
                # 删除过期会话
                del self.sessions[session_id]
        return None
    
    def delete_session(self, session_id):
        """删除会话"""
        if session_id in self.sessions:
            del self.sessions[session_id]
    
    def cleanup_expired_sessions(self):
        """清理过期会话"""
        current_time = datetime.now()
        expired_sessions = []
        for session_id, session_data in self.sessions.items():
            if current_time >= session_data['expiry']:
                expired_sessions.append(session_id)
        
        for session_id in expired_sessions:
            del self.sessions[session_id]
    
    def register_user(self, username, password, email=None):
        if username in self.users:
            return False, "用户名已存在"
        
        user_id = str(uuid.uuid4())
        salt = os.urandom(32)
        password_hash = hashlib.pbkdf2_hmac(
            'sha256', 
            password.encode('utf-8'), 
            salt, 
            100000
        )
        
        user_data = {
            'id': user_id,
            'username': username,
            'password_hash': password_hash.hex(),
            'salt': salt.hex(),
            'email': email,
            'created_at': datetime.now().isoformat(),
            'servers': [],
            'profile': {
                'avatar': '',
                'signature': '这个人很懒，什么都没有写～',
                'status': 'online'
            },
            'friends': []
        }
        
        self.users[username] = user_data
        self.save_users()
        return True, user_data
    
    def authenticate_user(self, username, password):
        if username not in self.users:
            return False, "用户不存在"
        
        user_data = self.users[username]
        salt = bytes.fromhex(user_data['salt'])
        password_hash = hashlib.pbkdf2_hmac(
            'sha256',
            password.encode('utf-8'),
            salt,
            100000
        )
        
        if password_hash.hex() == user_data['password_hash']:
            # 创建会话
            session_id = self.create_session(user_data)
            # 更新在线状态
            self.online_users[user_data['id']] = time.time()
            return True, {'user': user_data, 'session_id': session_id}
        else:
            return False, "密码错误"
    
    def get_user_by_id(self, user_id):
        for user in self.users.values():
            if user['id'] == user_id:
                return user
        return None
    
    def search_users(self, query):
        results = []
        for username, user_data in self.users.items():
            if query.lower() in username.lower():
                results.append({
                    'id': user_data['id'],
                    'username': username,
                    'profile': user_data['profile']
                })
        return results
    
    def update_profile(self, username, profile_data):
        if username not in self.users:
            return False, "用户不存在"
        
        self.users[username]['profile'].update(profile_data)
        self.save_users()
        return True, self.users[username]
    
    def update_online_status(self, user_id):
        self.online_users[user_id] = time.time()
        # 清理超时用户（5分钟未活动）
        current_time = time.time()
        timeout_users = [uid for uid, last_seen in self.online_users.items() 
                        if current_time - last_seen > 300]
        for uid in timeout_users:
            del self.online_users[uid]
    
    def get_online_users(self, server_id=None):
        self.update_online_status('dummy')  # 触发清理
        online_user_ids = list(self.online_users.keys())
        
        if server_id:
            server = server_manager.get_server(server_id)
            if server:
                server_user_ids = list(server['users'].keys())
                online_user_ids = [uid for uid in online_user_ids if uid in server_user_ids]
        
        online_users = []
        for user_data in self.users.values():
            if user_data['id'] in online_user_ids:
                online_users.append({
                    'id': user_data['id'],
                    'username': user_data['username'],
                    'profile': user_data['profile']
                })
        
        return online_users

# 好友管理
class FriendManager:
    def __init__(self):
        self.friends_file = os.path.join(CONFIG['data_dir'], CONFIG['friends_file'])
        self.load_friends()
    
    def load_friends(self):
        if os.path.exists(self.friends_file):
            with open(self.friends_file, 'r') as f:
                self.friends = json.load(f)
        else:
            self.friends = {}
    
    def save_friends(self):
        with open(self.friends_file, 'w') as f:
            json.dump(self.friends, f, indent=2)
    
    def add_friend(self, user_id, friend_id):
        if user_id not in self.friends:
            self.friends[user_id] = []
        
        if friend_id not in self.friends[user_id]:
            self.friends[user_id].append(friend_id)
            self.save_friends()
        
        # 双向好友关系
        if friend_id not in self.friends:
            self.friends[friend_id] = []
        
        if user_id not in self.friends[friend_id]:
            self.friends[friend_id].append(user_id)
            self.save_friends()
        
        return True
    
    def get_friends(self, user_id):
        return self.friends.get(user_id, [])
    
    def remove_friend(self, user_id, friend_id):
        if user_id in self.friends and friend_id in self.friends[user_id]:
            self.friends[user_id].remove(friend_id)
        
        if friend_id in self.friends and user_id in self.friends[friend_id]:
            self.friends[friend_id].remove(user_id)
        
        self.save_friends()
        return True

# 消息管理
class MessageManager:
    def __init__(self):
        pass
    
    def save_message(self, server_id, message_data):
        server_dir = os.path.join(CONFIG['data_dir'], server_id)
        messages_file = os.path.join(server_dir, 'messages.jsonl')
        
        with open(messages_file, 'a') as f:
            f.write(json.dumps(message_data) + '\n')
    
    def get_messages(self, server_id, channel='general', limit=100, offset=0):
        server_dir = os.path.join(CONFIG['data_dir'], server_id)
        messages_file = os.path.join(server_dir, 'messages.jsonl')
        
        if not os.path.exists(messages_file):
            return []
        
        messages = []
        with open(messages_file, 'r') as f:
            for line in f:
                try:
                    message = json.loads(line.strip())
                    if message.get('channel') == channel:
                        messages.append(message)
                except json.JSONDecodeError:
                    continue
        
        # 返回最新的消息
        return messages[-(limit + offset):-offset] if offset else messages[-limit:]
    
    def get_private_messages(self, server_id, user1, user2, limit=100):
        server_dir = os.path.join(CONFIG['data_dir'], server_id)
        messages_file = os.path.join(server_dir, 'messages.jsonl')
        
        if not os.path.exists(messages_file):
            return []
        
        messages = []
        with open(messages_file, 'r') as f:
            for line in f:
                try:
                    message = json.loads(line.strip())
                    if (message.get('type') == 'private' and 
                        ((message.get('from_user') == user1 and message.get('to_user') == user2) or
                         (message.get('from_user') == user2 and message.get('to_user') == user1))):
                        messages.append(message)
                except json.JSONDecodeError:
                    continue
        
        return messages[-limit:]

# AI 助手
class AIAssistant:
    def __init__(self):
        self.model = "qwen2.5:0.5b"
    
    def generate_response(self, message, context=None):
        try:
            prompt = f"用户说: {message}"
            if context:
                prompt += f"\n上下文: {context}"
            
            response = requests.post(
                f"{CONFIG['ollama_url']}/api/generate",
                json={
                    "model": self.model,
                    "prompt": prompt,
                    "stream": False
                },
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                return result.get('response', '抱歉，我现在无法回答这个问题。')
            else:
                return "AI服务暂时不可用。"
        except Exception as e:
            return f"AI服务错误: {str(e)}"

# 文件管理
class FileManager:
    def __init__(self):
        self.uploads_dir = CONFIG['uploads_dir']
    
    def save_file(self, file, filename):
        # 生成唯一文件名
        file_ext = filename.split('.')[-1] if '.' in filename else 'bin'
        unique_filename = f"{uuid.uuid4()}.{file_ext}"
        file_path = os.path.join(self.uploads_dir, unique_filename)
        
        file.save(file_path)
        return unique_filename
    
    def get_file_path(self, filename):
        return os.path.join(self.uploads_dir, filename)

# 初始化管理器
server_manager = ServerManager()
user_manager = UserManager()
friend_manager = FriendManager()
message_manager = MessageManager()
ai_assistant = AIAssistant()
file_manager = FileManager()

# API 路由
@app.route('/api/register', methods=['POST'])
def register():
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')
    email = data.get('email')
    
    if not username or not password:
        return jsonify({'success': False, 'message': '用户名和密码不能为空'})
    
    success, result = user_manager.register_user(username, password, email)
    if success:
        return jsonify({'success': True, 'user': result})
    else:
        return jsonify({'success': False, 'message': result})

@app.route('/api/login', methods=['POST'])
def login():
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')
    
    if not username or not password:
        return jsonify({'success': False, 'message': '用户名和密码不能为空'})
    
    success, result = user_manager.authenticate_user(username, password)
    if success:
        response = make_response(jsonify({
            'success': True, 
            'user': result['user'], 
            'session_id': result['session_id']
        }))
        # 设置HttpOnly Cookie，有效期7天
        response.set_cookie(
            'session_id',
            result['session_id'],
            max_age=7*24*60*60,
            httponly=True,
            secure=False,  # 开发环境设为False，生产环境应为True
            samesite='Lax'
        )
        return response
    else:
        return jsonify({'success': False, 'message': result})

@app.route('/api/verify_session', methods=['GET'])
def verify_session():
    """验证会话状态"""
    session_id = request.cookies.get('session_id')
    if not session_id:
        return jsonify({'success': False, 'message': '未找到会话'})
    
    user_data = user_manager.get_user_by_session(session_id)
    if user_data:
        user_manager.update_online_status(user_data['id'])
        return jsonify({'success': True, 'user': user_data})
    else:
        return jsonify({'success': False, 'message': '会话无效或已过期'})

@app.route('/api/logout', methods=['POST'])
def logout():
    """退出登录"""
    session_id = request.cookies.get('session_id')
    if session_id:
        user_manager.delete_session(session_id)
    
    response = make_response(jsonify({'success': True, 'message': '已退出登录'}))
    response.set_cookie('session_id', '', expires=0)
    return response

@app.route('/api/servers', methods=['GET'])
def get_servers():
    servers = server_manager.get_all_servers()
    return jsonify({'success': True, 'servers': servers})

@app.route('/api/servers/create', methods=['POST'])
def create_server():
    data = request.get_json()
    server_name = data.get('name')
    creator = data.get('creator')
    password = data.get('password')
    description = data.get('description', '')
    
    if not server_name or not creator:
        return jsonify({'success': False, 'message': '服务器名称和创建者不能为空'})
    
    server_id = str(uuid.uuid4())
    server_data = server_manager.create_server(server_id, server_name, creator, password, description)
    
    # 添加创建者到服务器用户列表
    server_data['users'][creator] = 'admin'
    server_manager.save_servers()
    
    return jsonify({'success': True, 'server': server_data})

@app.route('/api/servers/<server_id>/join', methods=['POST'])
def join_server(server_id):
    data = request.get_json()
    user_id = data.get('user_id')
    password = data.get('password')
    
    server = server_manager.get_server(server_id)
    if not server:
        return jsonify({'success': False, 'message': '服务器不存在'})
    
    # 检查密码
    if server.get('is_encrypted'):
        if not password or not server_manager.verify_server_password(server_id, password):
            return jsonify({'success': False, 'message': '服务器密码错误'})
    
    server['users'][user_id] = 'member'
    server_manager.save_servers()
    user_manager.update_online_status(user_id)
    
    return jsonify({'success': True, 'server': server})

@app.route('/api/servers/<server_id>/messages', methods=['GET'])
def get_server_messages(server_id):
    channel = request.args.get('channel', 'general')
    limit = int(request.args.get('limit', 100))
    offset = int(request.args.get('offset', 0))
    
    user_id = request.args.get('user_id')
    if user_id:
        user_manager.update_online_status(user_id)
    
    messages = message_manager.get_messages(server_id, channel, limit, offset)
    return jsonify({'success': True, 'messages': messages})

@app.route('/api/servers/<server_id>/messages/send', methods=['POST'])
def send_message(server_id):
    data = request.get_json()
    message_data = {
        'id': str(uuid.uuid4()),
        'server_id': server_id,
        'channel': data.get('channel', 'general'),
        'from_user': data.get('from_user'),
        'from_username': data.get('from_username'),
        'content': data.get('content'),
        'timestamp': datetime.now().isoformat(),
        'type': data.get('type', 'public')
    }
    
    if data.get('to_user'):
        message_data['to_user'] = data.get('to_user')
        message_data['type'] = 'private'
    
    if data.get('file_info'):
        message_data['file_info'] = data.get('file_info')
    
    message_manager.save_message(server_id, message_data)
    user_manager.update_online_status(data.get('from_user'))
    
    return jsonify({'success': True, 'message': message_data})

@app.route('/api/servers/<server_id>/online_users', methods=['GET'])
def get_online_users(server_id):
    user_id = request.args.get('user_id')
    if user_id:
        user_manager.update_online_status(user_id)
    
    online_users = user_manager.get_online_users(server_id)
    return jsonify({'success': True, 'online_users': online_users})

@app.route('/api/users/online', methods=['GET'])
def get_all_online_users():
    user_id = request.args.get('user_id')
    if user_id:
        user_manager.update_online_status(user_id)
    
    online_users = user_manager.get_online_users()
    return jsonify({'success': True, 'online_users': online_users})

@app.route('/api/private_messages', methods=['GET'])
def get_private_messages():
    server_id = request.args.get('server_id')
    user1 = request.args.get('user1')
    user2 = request.args.get('user2')
    limit = int(request.args.get('limit', 100))
    
    if not all([server_id, user1, user2]):
        return jsonify({'success': False, 'message': '缺少参数'})
    
    messages = message_manager.get_private_messages(server_id, user1, user2, limit)
    return jsonify({'success': True, 'messages': messages})

# 私聊功能API
@app.route('/api/private_chat/send', methods=['POST'])
def send_private_message():
    data = request.get_json()
    from_user = data.get('from_user')
    to_user = data.get('to_user')
    content = data.get('content')
    server_id = data.get('server_id')
    from_username = data.get('from_username')
    to_username = data.get('to_username')
    
    if not all([from_user, to_user, content, server_id]):
        return jsonify({'success': False, 'message': '参数不完整'})
    
    message_data = {
        'id': str(uuid.uuid4()),
        'server_id': server_id,
        'from_user': from_user,
        'from_username': from_username,
        'to_user': to_user,
        'to_username': to_username,
        'content': content,
        'timestamp': datetime.now().isoformat(),
        'type': 'private',
        'channel': 'private'
    }
    
    message_manager.save_message(server_id, message_data)
    user_manager.update_online_status(from_user)
    
    return jsonify({'success': True, 'message': message_data})

@app.route('/api/private_chat/messages', methods=['GET'])
def get_private_chat_messages():
    user1 = request.args.get('user1')
    user2 = request.args.get('user2')
    server_id = request.args.get('server_id')
    limit = int(request.args.get('limit', 100))
    
    if not all([user1, user2, server_id]):
        return jsonify({'success': False, 'message': '参数不完整'})
    
    messages = message_manager.get_private_messages(server_id, user1, user2, limit)
    return jsonify({'success': True, 'messages': messages})

@app.route('/api/users/search', methods=['GET'])
def search_users():
    query = request.args.get('q')
    if not query:
        return jsonify({'success': False, 'message': '搜索关键词不能为空'})
    
    results = user_manager.search_users(query)
    return jsonify({'success': True, 'users': results})

@app.route('/api/friends/add', methods=['POST'])
def add_friend():
    data = request.get_json()
    user_id = data.get('user_id')
    friend_id = data.get('friend_id')
    
    if not user_id or not friend_id:
        return jsonify({'success': False, 'message': '参数错误'})
    
    success = friend_manager.add_friend(user_id, friend_id)
    return jsonify({'success': success, 'message': '好友添加成功' if success else '好友添加失败'})

@app.route('/api/friends/list', methods=['GET'])
def get_friends():
    user_id = request.args.get('user_id')
    if not user_id:
        return jsonify({'success': False, 'message': '用户ID不能为空'})
    
    friend_ids = friend_manager.get_friends(user_id)
    friends = []
    for fid in friend_ids:
        user = user_manager.get_user_by_id(fid)
        if user:
            friends.append({
                'id': user['id'],
                'username': user['username'],
                'profile': user['profile']
            })
    
    return jsonify({'success': True, 'friends': friends})

@app.route('/api/profile/update', methods=['POST'])
def update_profile():
    data = request.get_json()
    username = data.get('username')
    profile_data = data.get('profile', {})
    
    success, result = user_manager.update_profile(username, profile_data)
    if success:
        return jsonify({'success': True, 'user': result})
    else:
        return jsonify({'success': False, 'message': result})

@app.route('/api/ai/chat', methods=['POST'])
def ai_chat():
    data = request.get_json()
    message = data.get('message')
    context = data.get('context')
    
    if not message:
        return jsonify({'success': False, 'message': '消息不能为空'})
    
    response = ai_assistant.generate_response(message, context)
    return jsonify({'success': True, 'response': response})

@app.route('/api/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return jsonify({'success': False, 'message': '没有文件'})
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'success': False, 'message': '没有选择文件'})
    
    filename = file_manager.save_file(file, file.filename)
    return jsonify({'success': True, 'filename': filename, 'original_name': file.filename})

@app.route('/api/download/<filename>')
def download_file(filename):
    try:
        return send_from_directory(file_manager.uploads_dir, filename)
    except FileNotFoundError:
        return jsonify({'success': False, 'message': '文件不存在'})

# 静态文件服务
@app.route('/')
def serve_default():
    return send_from_directory('.', 'pc_client.html')

@app.route('/pc')
def serve_pc_client():
    return send_from_directory('.', 'pc_client.html')

@app.route('/mobile')
def serve_mobile_client():
    return send_from_directory('.', 'mobile_client.html')



# 管理工具API
@app.route('/api/admin/users', methods=['GET'])
def get_all_users():
    """获取所有用户信息"""
    try:
        users_list = []
        for username, user_data in user_manager.users.items():
            # 检查用户是否在线
            is_online = user_data['id'] in user_manager.online_users
            last_seen = user_manager.online_users.get(user_data['id'], 0)
            
            users_list.append({
                'id': user_data['id'],
                'username': username,
                'email': user_data.get('email', ''),
                'online': is_online,
                'created_at': user_data['created_at'],
                'last_login': user_data.get('last_login'),
                'last_seen': last_seen if last_seen else None,
                'profile': user_data.get('profile', {}),
                'servers_count': len(user_data.get('servers', [])),
                'friends_count': len(user_data.get('friends', []))
            })
        
        return jsonify({'success': True, 'users': users_list})
    except Exception as e:
        return jsonify({'success': False, 'message': f'获取用户列表失败: {str(e)}'})

@app.route('/api/admin/users/<user_id>', methods=['GET'])
def get_user_detail(user_id):
    """获取用户详细信息"""
    try:
        user_data = None
        for username, user_info in user_manager.users.items():
            if user_info['id'] == user_id:
                user_data = user_info
                break
        
        if not user_data:
            return jsonify({'success': False, 'message': '用户不存在'})
        
        # 获取用户加入的服务器
        user_servers = []
        for server_id, server in server_manager.servers.items():
            if user_data['id'] in server.get('users', {}):
                user_servers.append({
                    'id': server_id,
                    'name': server['name'],
                    'role': server['users'][user_data['id']]
                })
        
        user_detail = {
            'id': user_data['id'],
            'username': next(username for username, info in user_manager.users.items() if info['id'] == user_id),
            'email': user_data.get('email', ''),
            'online': user_data['id'] in user_manager.online_users,
            'created_at': user_data['created_at'],
            'last_login': user_data.get('last_login'),
            'profile': user_data.get('profile', {}),
            'servers': user_servers,
            'friends': user_data.get('friends', [])
        }
        
        return jsonify({'success': True, 'user': user_detail})
    except Exception as e:
        return jsonify({'success': False, 'message': f'获取用户详情失败: {str(e)}'})

@app.route('/api/admin/users/<user_id>', methods=['DELETE'])
def delete_user(user_id):
    """删除用户"""
    try:
        # 找到对应的用户名
        target_username = None
        for username, user_info in user_manager.users.items():
            if user_info['id'] == user_id:
                target_username = username
                break
        
        if not target_username:
            return jsonify({'success': False, 'message': '用户不存在'})
        
        # 从所有服务器中移除用户
        for server_id, server in server_manager.servers.items():
            if user_id in server.get('users', {}):
                del server['users'][user_id]
        
        # 从好友关系中移除
        if user_id in friend_manager.friends:
            del friend_manager.friends[user_id]
        
        # 移除用户的好友关系
        for friend_list in friend_manager.friends.values():
            if user_id in friend_list:
                friend_list.remove(user_id)
        
        # 删除用户数据
        del user_manager.users[target_username]
        user_manager.save_users()
        server_manager.save_servers()
        friend_manager.save_friends()
        
        return jsonify({'success': True, 'message': '用户删除成功'})
    except Exception as e:
        return jsonify({'success': False, 'message': f'删除用户失败: {str(e)}'})

@app.route('/api/admin/stats', methods=['GET'])
def get_system_stats():
    """获取系统统计信息"""
    try:
        # 用户统计
        total_users = len(user_manager.users)
        online_users = len(user_manager.online_users)
        
        # 服务器统计
        servers = server_manager.servers
        total_servers = len(servers)
        
        # 计算活跃聊天（有用户的服务器）
        active_chats = 0
        for server in servers.values():
            if server.get('users') and len(server['users']) > 0:
                active_chats += 1
        
        # 消息统计（需要读取消息文件）
        total_messages = 0
        for server_id in servers.keys():
            server_dir = os.path.join(CONFIG['data_dir'], server_id)
            messages_file = os.path.join(server_dir, 'messages.jsonl')
            if os.path.exists(messages_file):
                with open(messages_file, 'r', encoding='utf-8') as f:
                    total_messages += len(f.readlines())
        
        stats = {
            'total_users': total_users,
            'online_users': online_users,
            'total_servers': total_servers,
            'active_chats': active_chats,
            'total_messages': total_messages,
            'system_status': 'running',
            'api_status': 'healthy',
            'uptime': '持续运行'
        }
        
        return jsonify({'success': True, 'stats': stats})
    except Exception as e:
        return jsonify({'success': False, 'message': f'获取统计信息失败: {str(e)}'})

@app.route('/api/admin/servers/<server_id>', methods=['DELETE'])
def delete_server(server_id):
    """删除服务器"""
    try:
        if server_id not in server_manager.servers:
            return jsonify({'success': False, 'message': '服务器不存在'})
        
        # 删除服务器数据
        del server_manager.servers[server_id]
        server_manager.save_servers()
        
        # 删除服务器目录
        server_dir = os.path.join(CONFIG['data_dir'], server_id)
        if os.path.exists(server_dir):
            import shutil
            shutil.rmtree(server_dir)
        
        return jsonify({'success': True, 'message': '服务器删除成功'})
    except Exception as e:
        return jsonify({'success': False, 'message': f'删除服务器失败: {str(e)}'})

@app.route('/api/admin/messages/stats', methods=['GET'])
def get_message_stats():
    """获取消息统计"""
    try:
        servers = server_manager.servers
        total_messages = 0
        private_messages = 0
        public_messages = 0
        
        for server_id, server in servers.items():
            server_dir = os.path.join(CONFIG['data_dir'], server_id)
            messages_file = os.path.join(server_dir, 'messages.jsonl')
            
            if os.path.exists(messages_file):
                with open(messages_file, 'r', encoding='utf-8') as f:
                    for line in f:
                        try:
                            message = json.loads(line.strip())
                            total_messages += 1
                            if message.get('type') == 'private':
                                private_messages += 1
                            else:
                                public_messages += 1
                        except:
                            continue
        
        # 今日消息（简化计算）
        today_messages = int(total_messages * 0.1)  # 模拟数据
        
        stats = {
            'total_messages': total_messages,
            'today_messages': today_messages,
            'private_messages': private_messages,
            'public_messages': public_messages,
            'server_distribution': {}
        }
        
        # 服务器消息分布
        for server_id, server in servers.items():
            server_dir = os.path.join(CONFIG['data_dir'], server_id)
            messages_file = os.path.join(server_dir, 'messages.jsonl')
            server_messages = 0
            
            if os.path.exists(messages_file):
                with open(messages_file, 'r', encoding='utf-8') as f:
                    server_messages = len(f.readlines())
            
            stats['server_distribution'][server['name']] = server_messages
        
        return jsonify({'success': True, 'stats': stats})
    except Exception as e:
        return jsonify({'success': False, 'message': f'获取消息统计失败: {str(e)}'})

@app.route('/<path:filename>')
def serve_static(filename):
    return send_from_directory('.', filename)

def cleanup_online_users():
    """定期清理离线用户"""
    while True:
        time.sleep(60)
        user_manager.update_online_status('dummy')  # 触发清理

def cleanup_sessions():
    """定期清理过期会话"""
    while True:
        time.sleep(3600)  # 每小时清理一次
        user_manager.cleanup_expired_sessions()

if __name__ == '__main__':
    # 启动清理线程
    cleanup_thread = threading.Thread(target=cleanup_online_users, daemon=True)
    cleanup_thread.start()
    
    session_cleanup_thread = threading.Thread(target=cleanup_sessions, daemon=True)
    session_cleanup_thread.start()
    
    print(f"启动聊天服务器在 http://localhost:{CONFIG['port']}")
    print("电脑客户端: http://localhost:9074/pc")
    print("手机客户端: http://localhost:9074/mobile")
    print("开发团队: DeepLora团队")
    app.run(
        host=CONFIG['host'],
        port=CONFIG['port'],
        debug=True,
        threaded=True
    )