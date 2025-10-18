#!/usr/bin/env python3
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
    
    print("\n🎯 测试完成！")

if __name__ == "__main__":
    test_cookie_functionality()
