FROM amazon/aws-lambda-python:3.9 as base

FROM base AS rmapi
RUN yum update -y
RUN yum install -y golang
RUN GO111MODULE=on go get github.com/juruen/rmapi@latest

FROM base as final
COPY --from=rmapi /root/go/bin/rmapi /usr/bin/rmapi
RUN yum update -y \
  && yum install -y \
  cairo \
  pango \
  php-pear php-devel gcc \
  ImageMagick ImageMagick-devel ImageMagick-perl \
  qpdf \
  ghostscript \  
  poppler-utils \  
  && yum clean all \
  && rm -rf /var/cache/yum

# Required for Readability.js
RUN curl -sL https://rpm.nodesource.com/setup_14.x | bash - \
  && yum install -y nodejs

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY main.py ./

CMD [ "main.lambda_handler" ]
