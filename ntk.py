#!/usr/bin/env python3
"""
星界聊天系统 - Cookie会话修复脚本
修复Cookie无法保存登录状态的问题
DeepLora团队
"""

import os
import datetime

def backup_server_file():
    """备份原始server.py文件"""
    if os.path.exists('server.py'):
        backup_name = f"server_backup_cookie_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.py"
        with open('server.py', 'r', encoding='utf-8') as f:
            content = f.read()
        with open(backup_name, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"✅ 已备份原文件: {backup_name}")
        return True
    else:
        print("❌ 未找到server.py文件")
        return False

def fix_cookie_issues():
    """修复Cookie相关问题"""
    
    cookie_fixes = '''
# Cookie和会话修复
@app.route('/api/login', methods=['POST'])
def login():
    """修复后的登录接口"""
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
        # 修复Cookie设置 - 添加domain和path
        response.set_cookie(
            'session_id',
            result['session_id'],
            max_age=7*24*60*60,  # 7天
            httponly=True,
            secure=False,
            samesite='Lax',
            path='/',
            domain=None  # 当前域名
        )
        # 更新最后登录时间
        user_manager.update_last_login(username)
        return response
    else:
        return jsonify({'success': False, 'message': result})

@app.route('/api/verify_session', methods=['GET', 'POST'])
def verify_session():
    """修复会话验证接口，支持GET和POST"""
    session_id = request.cookies.get('session_id')
    if not session_id:
        return jsonify({'success': False, 'message': '未找到会话'})
    
    user_data = user_manager.get_user_by_session(session_id)
    if user_data:
        user_manager.update_online_status(user_data['id'])
        return jsonify({'success': True, 'user': user_data})
    else:
        # 清除无效的Cookie
        response = make_response(jsonify({'success': False, 'message': '会话无效或已过期'}))
        response.set_cookie('session_id', '', expires=0)
        return response

@app.route('/api/logout', methods=['POST'])
def logout():
    """修复退出登录接口"""
    session_id = request.cookies.get('session_id')
    if session_id:
        user_manager.delete_session(session_id)
    
    response = make_response(jsonify({'success': True, 'message': '已退出登录'}))
    response.set_cookie('session_id', '', expires=0, path='/', domain=None)
    return response

# 增强的UserManager类方法
def update_last_login(self, username):
    """更新用户最后登录时间"""
    if username in self.users:
        self.users[username]['last_login'] = datetime.now().isoformat()
        self.save_users()

def create_session(self, user_data):
    """创建会话并返回session_id"""
    session_id = str(uuid.uuid4())
    expiry = datetime.now() + timedelta(days=7)
    self.sessions[session_id] = {
        'user_data': user_data,
        'expiry': expiry
    }
    # 立即保存会话（在实际项目中应该持久化到数据库）
    return session_id

def get_user_by_session(self, session_id):
    """根据session_id获取用户信息"""
    if session_id in self.sessions:
        session = self.sessions[session_id]
        # 检查会话是否过期
        if datetime.now() < session['expiry']:
            # 更新会话过期时间（滑动过期）
            session['expiry'] = datetime.now() + timedelta(days=7)
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
'''

    return cookie_fixes

def update_client_files():
    """更新客户端文件以正确处理Cookie"""
    
    # 修复pc_client.html
    if os.path.exists('pc_client.html'):
        with open('pc_client.html', 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 修复自动登录函数
        if 'autoLogin()' in content:
            # 替换autoLogin函数
            new_auto_login = '''
        // 自动登录 - 修复版本
        async function autoLogin() {
            const sessionId = getCookie('session_id');
            if (!sessionId) {
                return;
            }

            try {
                const response = await fetch(`${API_BASE}/verify_session`, {
                    method: 'GET',
                    credentials: 'include'  // 重要：包含Cookie
                });

                const data = await response.json();
                if (data.success) {
                    currentUser = data.user;
                    updateUI();
                    loadServers();
                    loadFriends();
                    showNotification('自动登录成功！');
                } else {
                    // 清除无效的Cookie
                    deleteCookie('session_id');
                }
            } catch (error) {
                console.error('自动登录失败:', error);
                // 网络错误时也清除Cookie，避免循环尝试
                deleteCookie('session_id');
            }
        }'''
            
            # 简单的字符串替换（实际项目中应该用更精确的方法）
            content = content.replace('async function autoLogin() {', 'async function autoLogin_OLD() {')
            # 在适当位置插入新的autoLogin函数
            script_start = content.find('<script>')
            if script_start != -1:
                insert_pos = content.find('// 自动登录', script_start)
                if insert_pos != -1:
                    content = content[:insert_pos] + new_auto_login + content[insert_pos:]
        
        with open('pc_client_fixed.html', 'w', encoding='utf-8') as f:
            f.write(content)
        print("✅ 已创建修复后的PC客户端: pc_client_fixed.html")
    
    # 修复mobile_client.html
    if os.path.exists('mobile_client.html'):
        with open('mobile_client.html', 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 同样修复移动端的autoLogin函数
        if 'autoLogin()' in content:
            new_auto_login = '''
        // 自动登录 - 修复版本
        async function autoLogin() {
            try {
                const response = await fetch(`${API_BASE}/verify_session`, {
                    method: 'GET',
                    credentials: 'include'
                });

                const data = await response.json();
                if (data.success) {
                    currentUser = data.user;
                    updateUI();
                    loadServers();
                    loadFriends();
                    updateHeaderActions();
                    showNotification('自动登录成功！');
                } else {
                    deleteCookie('session_id');
                }
            } catch (error) {
                console.error('自动登录失败:', error);
                deleteCookie('session_id');
            }
        }'''
            
            content = content.replace('async function autoLogin() {', 'async function autoLogin_OLD() {')
            script_start = content.find('<script>')
            if script_start != -1:
                insert_pos = content.find('// 自动登录', script_start)
                if insert_pos != -1:
                    content = content[:insert_pos] + new_auto_login + content[insert_pos:]
        
        with open('mobile_client_fixed.html', 'w', encoding='utf-8') as f:
            f.write(content)
        print("✅ 已创建修复后的移动客户端: mobile_client_fixed.html")

def create_test_script():
    """创建Cookie测试脚本"""
    
    test_script = '''#!/usr/bin/env python3
"""
Cookie功能测试脚本
测试登录、会话验证和Cookie功能
"""

import requests
import json

def test_cookie_functionality():
    base_url = "http://localhost:9074/api"
    session = requests.Session()  # 使用Session保持Cookie
    
    print("🧪 开始测试Cookie功能...")
    
    # 1. 测试注册
    print("1. 测试用户注册...")
    reg_data = {
        "username": "testuser_cookie",
        "password": "testpass123"
    }
    
    try:
        reg_response = session.post(f"{base_url}/register", json=reg_data)
        print(f"   注册响应: {reg_response.status_code}")
        if reg_response.status_code == 200:
            print("   ✅ 注册成功")
        else:
            print(f"   ❌ 注册失败: {reg_response.text}")
    except Exception as e:
        print(f"   ❌ 注册请求失败: {e}")
    
    # 2. 测试登录
    print("2. 测试用户登录...")
    login_data = {
        "username": "testuser_cookie",
        "password": "testpass123"
    }
    
    try:
        login_response = session.post(f"{base_url}/login", json=login_data)
        print(f"   登录响应: {login_response.status_code}")
        
        if login_response.status_code == 200:
            result = login_response.json()
            if result.get('success'):
                print("   ✅ 登录成功")
                print(f"   收到的Cookie: {session.cookies.get_dict()}")
            else:
                print(f"   ❌ 登录失败: {result.get('message')}")
        else:
            print(f"   ❌ 登录HTTP错误: {login_response.text}")
    except Exception as e:
        print(f"   ❌ 登录请求失败: {e}")
    
    # 3. 测试会话验证
    print("3. 测试会话验证...")
    try:
        verify_response = session.get(f"{base_url}/verify_session")
        print(f"   验证响应: {verify_response.status_code}")
        
        if verify_response.status_code == 200:
            result = verify_response.json()
            if result.get('success'):
                print("   ✅ 会话验证成功")
                print(f"   用户信息: {result.get('user', {}).get('username')}")
            else:
                print(f"   ❌ 会话验证失败: {result.get('message')}")
        else:
            print(f"   ❌ 验证HTTP错误: {verify_response.text}")
    except Exception as e:
        print(f"   ❌ 验证请求失败: {e}")
    
    # 4. 测试退出登录
    print("4. 测试退出登录...")
    try:
        logout_response = session.post(f"{base_url}/logout")
        print(f"   退出响应: {logout_response.status_code}")
        
        if logout_response.status_code == 200:
            result = logout_response.json()
            if result.get('success'):
                print("   ✅ 退出登录成功")
            else:
                print(f"   ❌ 退出失败: {result.get('message')}")
        else:
            print(f"   ❌ 退出HTTP错误: {logout_response.text}")
    except Exception as e:
        print(f"   ❌ 退出请求失败: {e}")
    
    # 5. 测试退出后的会话验证
    print("5. 测试退出后的会话验证...")
    try:
        verify_after_logout = session.get(f"{base_url}/verify_session")
        print(f"   退出后验证响应: {verify_after_logout.status_code}")
        
        if verify_after_logout.status_code == 200:
            result = verify_after_logout.json()
            if not result.get('success'):
                print("   ✅ 退出后会话正确失效")
            else:
                print("   ❌ 退出后会话仍然有效")
        else:
            print(f"   ❌ 验证HTTP错误: {verify_after_logout.text}")
    except Exception as e:
        print(f"   ❌ 验证请求失败: {e}")
    
    print("\\n🎯 测试完成！")

if __name__ == "__main__":
    test_cookie_functionality()
'''
    
    with open('test_cookie.py', 'w', encoding='utf-8') as f:
        f.write(test_script)
    
    print("✅ 已创建Cookie测试脚本: test_cookie.py")

def apply_cookie_fixes():
    """应用Cookie修复"""
    
    if not backup_server_file():
        return False
    
    try:
        with open('server.py', 'r', encoding='utf-8') as f:
            content = f.read()
        
        print("🔧 正在修复Cookie问题...")
        
        # 检查是否已经修复过
        if '修复后的登录接口' in content:
            print("⚠️  看起来已经修复过了，跳过修复")
            return True
        
        # 1. 替换登录路由
        login_route_start = content.find('@app.route(\'/api/login\'')
        if login_route_start != -1:
            login_route_end = content.find('def login():', login_route_start)
            if login_route_end != -1:
                # 找到整个登录函数
                function_start = login_route_end
                function_end = content.find('@app.route', function_start + 1)
                if function_end == -1:
                    function_end = len(content)
                
                # 替换登录函数
                new_login = '''@app.route('/api/login', methods=['POST'])
def login():
    """修复后的登录接口"""
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
        # 修复Cookie设置
        response.set_cookie(
            'session_id',
            result['session_id'],
            max_age=7*24*60*60,
            httponly=True,
            secure=False,
            samesite='Lax',
            path='/',
            domain=None
        )
        # 更新最后登录时间
        user_manager.update_last_login(username)
        return response
    else:
        return jsonify({'success': False, 'message': result})'''
                
                content = content[:login_route_start] + new_login + content[function_end:]
        
        # 2. 替换会话验证路由
        verify_route_start = content.find('@app.route(\'/api/verify_session\'')
        if verify_route_start != -1:
            verify_route_end = content.find('def verify_session():', verify_route_start)
            if verify_route_end != -1:
                function_end = content.find('@app.route', verify_route_end + 1)
                if function_end == -1:
                    function_end = len(content)
                
                new_verify = '''@app.route('/api/verify_session', methods=['GET', 'POST'])
def verify_session():
    """修复会话验证接口，支持GET和POST"""
    session_id = request.cookies.get('session_id')
    if not session_id:
        return jsonify({'success': False, 'message': '未找到会话'})
    
    user_data = user_manager.get_user_by_session(session_id)
    if user_data:
        user_manager.update_online_status(user_data['id'])
        return jsonify({'success': True, 'user': user_data})
    else:
        # 清除无效的Cookie
        response = make_response(jsonify({'success': False, 'message': '会话无效或已过期'}))
        response.set_cookie('session_id', '', expires=0)
        return response'''
                
                content = content[:verify_route_start] + new_verify + content[function_end:]
        
        # 3. 替换退出登录路由
        logout_route_start = content.find('@app.route(\'/api/logout\'')
        if logout_route_start != -1:
            logout_route_end = content.find('def logout():', logout_route_start)
            if logout_route_end != -1:
                function_end = content.find('@app.route', logout_route_end + 1)
                if function_end == -1:
                    function_end = len(content)
                
                new_logout = '''@app.route('/api/logout', methods=['POST'])
def logout():
    """修复退出登录接口"""
    session_id = request.cookies.get('session_id')
    if session_id:
        user_manager.delete_session(session_id)
    
    response = make_response(jsonify({'success': True, 'message': '已退出登录'}))
    response.set_cookie('session_id', '', expires=0, path='/', domain=None)
    return response'''
                
                content = content[:logout_route_start] + new_logout + content[function_end:]
        
        # 4. 确保UserManager有update_last_login方法
        if 'def update_last_login(' not in content:
            # 在UserManager类中添加方法
            class_start = content.find('class UserManager:')
            if class_start != -1:
                # 找到authenticate_user方法结束
                auth_method_start = content.find('def authenticate_user(', class_start)
                if auth_method_start != -1:
                    auth_method_end = content.find('def ', auth_method_start + 1)
                    if auth_method_end == -1:
                        auth_method_end = len(content)
                    
                    new_method = '''
    def update_last_login(self, username):
        """更新用户最后登录时间"""
        if username in self.users:
            self.users[username]['last_login'] = datetime.now().isoformat()
            self.save_users()'''
                    
                    content = content[:auth_method_end] + new_method + content[auth_method_end:]
        
        # 保存修复后的文件
        with open('server.py', 'w', encoding='utf-8') as f:
            f.write(content)
        
        print("✅ Cookie修复完成！")
        return True
        
    except Exception as e:
        print(f"❌ 修复过程中出错: {str(e)}")
        return False

def main():
    """主函数"""
    print("🚀 星界聊天系统 - Cookie会话修复脚本")
    print("=" * 50)
    print("📝 正在修复Cookie无法保存登录状态的问题...")
    
    if apply_cookie_fixes():
        update_client_files()
        create_test_script()
        print("\n🎉 修复完成！")
        print("\n📋 使用说明：")
        print("1. 重启聊天服务器: python server.py")
        print("2. 测试Cookie功能: python test_cookie.py")
        print("3. 使用修复后的客户端:")
        print("   - PC端: http://localhost:9074/pc_client_fixed.html")
        print("   - 移动端: http://localhost:9074/mobile_client_fixed.html")
        print("   - 管理工具: http://localhost:9074/admin_tool_fixed.html")
        print("\n🔧 修复内容：")
        print("   • 修复Cookie设置（添加path和domain）")
        print("   • 增强会话验证（支持GET/POST）")
        print("   • 改进自动登录逻辑")
        print("   • 添加最后登录时间记录")
        print("   • 创建测试脚本验证功能")
    else:
        print("\n❌ 修复失败，请检查错误信息")

if __name__ == "__main__":
    main()