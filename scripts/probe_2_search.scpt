-- probe_2_search.scpt
-- 目的：测试能否在 Mac 微信中搜索联系人
-- ⚠️ 警告：会把搜索词输入搜索框，但**不会**发送消息
-- 用法：osascript probe_2_search.scpt 张三
-- 收到："找到联系人：张三" 或 "未找到"

on run argv
    set targetName to item 1 of argv

    tell application "WeChat"
        activate
    end tell

    delay 0.5

    tell application "System Events"
        tell process "WeChat"
            -- 打开搜索（⌘F）
            keystroke "f" using {command down}
            delay 0.3

            -- 清空搜索框
            keystroke "a" using {command down}
            key code 51 -- backspace
            delay 0.2

            -- 输入联系人名
            keystroke targetName
            delay 0.8

            -- 检查搜索结果
            -- Mac 微信搜索结果在主窗口列表中
            -- 这里简化处理：返回 "搜索已输入"
            return "✓ 搜索词已输入：" & targetName
        end tell
    end tell
end run