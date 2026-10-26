FROM python:3.13-alpine
RUN apk add --no-cache ffmpeg tzdata
COPY recorder.py /app/recorder.py
CMD ["python3", "-u", "/app/recorder.py"]
