-- probe_1_focus.scpt
-- 目的：验证 AppleScript 能激活并控制 Mac 微信
-- 风险：0（只切换窗口，不发消息）

tell application "WeChat"
    activate
end tell

delay 0.5

tell application "System Events"
    tell process "WeChat"
        -- 检查微信进程存在
        set wechatExists to exists
        if wechatExists then
            -- 获取窗口标题
            set windowTitle to name of front window
            return "✓ 微信已激活，窗口标题：" & windowTitle
        else
            return "✗ 微信进程不存在，请先打开微信"
        end if
    end tell
end tell