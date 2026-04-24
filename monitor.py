import requests
import time
import sys
import re

def get_video_stats(bvid):
    """
    获取B站视频数据，包括评论数。
    """
    # 提取BV号（防止传入完整链接）
    match = re.search(r'BV[A-Za-z0-9]+', bvid)
    if match:
        bvid = match.group(0)

    url = f"https://api.bilibili.com/x/web-interface/view?bvid={bvid}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    
    try:
        response = requests.get(url, headers=headers)
        data = response.json()
        
        if data['code'] == 0:
            stats = data['data']['stat']
            title = data['data']['title']
            return {
                'title': title,
                'reply': stats['reply'],
                'view': stats['view']
            }
        else:
            print(f"错误: {data['message']}")
            return None
    except Exception as e:
        print(f"发生异常: {e}")
        return None

def monitor(bvid, interval=10):
    # 再次确保提取了BV号用于显示
    match = re.search(r'BV[A-Za-z0-9]+', bvid)
    clean_bvid = match.group(0) if match else bvid
    
    print(f"开始监测视频 [{clean_bvid}] 的评论数量...")
    last_reply = -1
    
    try:
        while True:
            stats = get_video_stats(bvid)
            if stats:
                current_reply = stats['reply']
                title = stats['title']
                timestamp = time.strftime("%H:%M:%S", time.localtime())
                
                if last_reply == -1:
                    print(f"[{timestamp}] 视频: {title}")
                    print(f"[{timestamp}] 当前评论数: {current_reply}")
                elif current_reply != last_reply:
                    diff = current_reply - last_reply
                    change = f"+{diff}" if diff > 0 else f"{diff}"
                    print(f"[{timestamp}] 评论数更新: {current_reply} ({change})")
                
                last_reply = current_reply
            
            time.sleep(interval)
    except KeyboardInterrupt:
        print("\n已停止监测。")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        target = sys.argv[1]
    else:
        target = input("请输入B站视频BV号或链接: ").strip()
    
    if not target:
        print("输入不能为空！")
    else:
        monitor(target)
