-- send_to_wechat.applescript v5
-- 修复：用 Tab 切换到搜索结果，方向键选择联系人
-- 用法：osascript send_to_wechat.applescript <联系人> <消息内容>

on run argv
    set targetName to item 1 of argv
    set messageText to item 2 of argv

    tell application "WeChat"
        activate
    end tell

    delay 0.8

    set the clipboard to targetName

    tell application "System Events"
        tell process "WeChat"
            -- 打开搜索
            keystroke "f" using {command down}
            delay 0.5

            -- 清空并粘贴联系人名
            keystroke "a" using {command down}
            key code 51
            delay 0.3
            keystroke "v" using {command down}
            delay 1.0

            -- Tab 从搜索框切换到搜索结果列表
            key code 48
            delay 0.5

            -- ↓ 选第一个结果
            key code 125
            delay 0.3

            -- Enter 打开对话
            key code 36
            delay 0.6

            -- 保险：再按一次 Enter（微信"发消息"按钮）
            key code 36
            delay 0.5

            -- 粘贴消息
            set the clipboard to messageText
            keystroke "v" using {command down}
            delay 0.5

            -- 发送
            key code 36

            return "✓ 消息已发送到：" & targetName
        end tell
    end tell
end run