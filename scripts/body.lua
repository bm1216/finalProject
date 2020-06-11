wrk.headers["Content-Type"] = "application/json"
wrk.body = '{"func": "function_one"}'


counter = 0

response = function(status, headers, body)
  if status == 200 then
    counter = counter + 1
  else
    print(body)
  end

  return wrk.format(counter)

