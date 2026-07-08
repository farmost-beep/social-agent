-- probe_3_send.scpt
-- 目的：测试**真正发送**消息（最危险，先 dry-run 验证）
-- ⚠️ 警告：这条会**真的发消息**，请先用 test 联系人测试
-- 用法：osascript probe_3_send.scpt "文件传输助手" "test from probe"

on run argv
    set targetName to item 1 of argv
    set messageText to item 2 of argv

    tell application "WeChat"
        activate
    end tell

    delay 0.5

    tell application "System Events"
        tell process "WeChat"
            -- 打开搜索
            keystroke "f" using {command down}
            delay 0.3
            keystroke "a" using {command down}
            key code 51
            delay 0.2

            -- 搜索联系人
            keystroke targetName
            delay 0.8

            -- 按回车选中第一个结果
            key code 36
            delay 0.5

            -- ⚠️ 取消搜索栏（按 ESC），避免消息输入到搜索框
            key code 53 -- ESC
            delay 0.3

            -- 输入消息
            keystroke messageText
            delay 0.3

            -- 发送（按回车）
            key code 36

            return "✓ 消息已发送到：" & targetName
        end tell
    end tell
end run