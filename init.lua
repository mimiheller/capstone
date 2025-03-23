local copiedText = nil

local socket = require("socket")
local client 

-- Function to establish/reconnect the TCP connection
local function connectToServer()
    if not client or client:getstats() == nil then  -- Check if connection is active
        client = socket.connect("localhost", 5050)
        if client then
            client:settimeout(0)  -- Set non-blocking mode
            hs.alert.show("Connected to Python server")
        else
            hs.alert.show("Failed to connect to Python server")
        end
    end
end

hs.hotkey.bind({"cmd"}, "G", function()
    connectToServer() 

    hs.alert.show("Fetching Completion...")    

    -- Select All (CMD + A)
    hs.eventtap.keyStroke({"cmd"}, "a")
    hs.timer.usleep(100000)

    -- Copy (CMD + C)
    hs.eventtap.keyStroke({"cmd"}, "c")
    hs.timer.usleep(200000)

    -- Read clipboard content
    copiedText = hs.pasteboard.getContents()
    
    if copiedText and copiedText ~= "" then
        -- Escape quotes
        copiedText = copiedText:gsub("'", "'\\''")
        
        -- send copiedText through socket to client.py
        if client then 
            
            local success, send_err = client:send(copiedText .. "\n")
            
            if not success then 
                hs.alert.show("Failed to send data: " .. send_err)
                client = nil
            end

            -- local response, recv_err = client:receive()
            
            -- if response then
            --     hs.console.log("Response" .. response)
            --     hs.pasteboard.setContents(response)
            --     hs.alert.show("Finalizing Completion...")
            --     hs.eventtap.keyStroke({"cmd"}, "v")
            --     hs.alert.show("Pasting Completion!")
            -- else 
            --     hs.alert.show("Failed to recieve response" .. (recv_err or "Unknown error"))
            -- end

        else 
            hs.alert.show("No active connection to server")
        end
    
    else
        hs.alert.show("Clipboard empty!")
    end

end)

-- Hotkey to reject result
hs.hotkey.bind({"cmd"}, "L", function()
    if completionReady then 
        hs.eventtap.keyStroke({"cmd"}, "a")  -- Select all text
        hs.timer.usleep(100000)  -- Wait for selection to finish
        hs.pasteboard.setContents(copiedText)
        hs.eventtap.keyStroke({"cmd"}, "v")
        -- hs.eventtap.keyStroke({}, "delete")  -- Simulate the delete key
        hs.alert.show("Text deleted!")

        completionReady = false  -- Reset state
    else 
        hs.alert.show("No text generated!")
    end
end)