json = require('cjson')

wrk.headers["Content-Type"] = "application/json"
wrk.body = '{"func": "function_two"}'


counter = 0
my_table = {}

response = function(status, headers, body)
  if status == 200 then
    body = json.decode(body)
    ip = body["value"]
    print(type(body))
    print(ip)
    if my_table[ip] ~= nil then 
      my_table[ip] = my_table[ip] + 1
    else
      my_table[ip] = 0
    end
    counter = counter + 1
    print(my_table)
  else
    print(body)
  end

  return wrk.format(counter)
end

