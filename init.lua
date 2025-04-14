local copiedText = nil
local socket = require("socket")
local client 
local completionReady = false -- track if output is ready 

-- Function to establish/reconnect the TCP connection
local function connectToServer()
    local conn = socket.connect("localhost", 5050)
    if conn then
        conn:settimeout(5)
        hs.alert.show("Connected to Python server")
    else
        hs.alert.show("Failed to connect to Python server")
    end
    return conn
end
--     if not client or client:getstats() == nil then  -- Check if connection is active
--         client = socket.connect("localhost", 5050)
--         if client then
--             client:settimeout(5)  -- Set non-blocking mode
--             hs.alert.show("Connected to Python server")
--         else
--             hs.alert.show("Failed to connect to Python server")
--         end
--     end
-- end

hs.hotkey.bind({"cmd"}, "G", function()
    if completionReady then
        -- remove preview markers
        hs.eventtap.keyStroke({"cmd"}, "a")
        hs.timer.usleep(100000)
        hs.eventtap.keyStroke({"cmd"}, "c")
        hs.timer.usleep(200000)

        local copiedText = hs.pasteboard.getContents()
        local cleanedText = copiedText:gsub("<<<PREVIEW>>> ", ""):gsub(" <<<END>>>", "") .. " "
        cleanedText = " " .. cleanedText

        hs.pasteboard.setContents(cleanedText)
        hs.alert.show("Completion Accepted...")
        hs.eventtap.keyStroke({"cmd"}, "v")
        completionReady = false -- Reset State




    else
        client = connectToServer()
        if not client then return end  

        hs.alert.show("Fetching Completion...")    

        -- Select All (CMD + A)
        hs.eventtap.keyStroke({"cmd"}, "a")
        hs.timer.usleep(100000)

        -- Copy (CMD + C)
        hs.eventtap.keyStroke({"cmd"}, "c")
        hs.timer.usleep(200000)

        hs.eventtap.keyStroke({}, "right")
        hs.timer.usleep(100000)

        -- Read clipboard content
        copiedText = hs.pasteboard.getContents()
        
        if copiedText and copiedText ~= "" then
            -- Escape quotes
            copiedText = copiedText:gsub("'", "'\\''")
            
            -- send copiedText through socket to client.py
            if client then 
                local success, send_err = client:send(copiedText .. "\n")

                if success then 
                    -- Keep checking for an ACK until received
                    while true do
                        local ack, ack_err = client:receive()
                        if ack then
                            break  -- Exit loop once ACK is received
                        else
                            hs.timer.usleep(500000)  -- Sleep for 500ms before checking again
                        end
                    end
                    
                    -- Read response from local file
                    local file = io.open("/Users/ameliaheller/Desktop/capstone_test_final/received_text_FPGA.txt", "r")
                    local response 

                    if file then 
                        response = file:read("*a")  
                        file:close()  -- Close the file
                        os.remove("received_text_FPGA.txt") 
                        -- Debugging: Check if response is valid
                    else 
                        hs.alert.show("Failed to open file")
                    end
                    
                    if response and response ~= "" then
                        local preview = "<<<PREVIEW>>> " .. response .. " <<<END>>>"
                        hs.pasteboard.setContents(preview)
                        hs.eventtap.keyStroke({"cmd"}, "v")
                        completionReady = true -- Enable paste on next Cmd + G
                    else
                        hs.alert.show("File Read Failed: Empty or nil response")
                    end

                else
                    hs.alert.show("Failed to send data: " .. send_err)
                end
                
                client:close()
                client = nil

            end

        else
            hs.alert.show("Clipboard empty!")
        end
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
        hs.alert.show("Completion Rejected...")

        completionReady = false  -- Reset state
    else 
        hs.alert.show("No text generated!")
    end
end)

