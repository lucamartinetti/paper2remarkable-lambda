
# build
```
podman build -t p2r .
```

# run
```
podman run -p 9000:8080  p2r
curl -XPOST "http://localhost:9000/2015-03-31/functions/function/invocations" -d '{"queryStringParameters": { "url": "https://aws.amazon.com/premiumsupport/knowledge-center/lambda-linux-binary-package/"}}'
```

# deploy
```
aws ecr get-login-password --region eu-west-2 | podman login --username AWS --password-stdin 334807166393.dkr.ecr.eu-west-2.amazonaws.com
podman push p2r 334807166393.dkr.ecr.eu-west-2.amazonaws.com/paper2remarkable-lambda:latest

```