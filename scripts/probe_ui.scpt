-- probe_ui.scpt — 探测 Mac 微信 UI 元素层级
tell application "WeChat"
    activate
end tell
delay 1

tell application "System Events"
    tell process "WeChat"
        set uiElements to entire contents of window 1
        set output to ""
        repeat with el in uiElements
            set elemRole to role of el
            if elemRole contains "Search" or elemRole contains "TextField" or elemRole contains "List" or elemRole contains "Outline" or elemRole contains "Button" or elemRole contains "Row" or elemRole contains "StaticText" then
                try
                    set elemDesc to description of el
                on error
                    set elemDesc to ""
                end try
                try
                    set elemVal to value of el
                on error
                    set elemVal to ""
                end try
                set output to output & elemRole & " | " & elemDesc & " | " & elemVal & return
            end if
        end repeat
        return output
    end tell
end tell