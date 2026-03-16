FROM python:3.13-slim

# 系统依赖：Chromium headless（kaleido 图片导出需要）
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        chromium \
        fonts-noto-cjk \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 先装依赖（利用 Docker 层缓存）
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制项目
COPY . .

# 入口脚本
RUN chmod +x docker-entrypoint.sh

# 环境变量
ENV PYTHONIOENCODING=utf-8 \
    PYTHONUNBUFFERED=1 \
    STREAMLIT_SERVER_HEADLESS=true

EXPOSE 8501

ENTRYPOINT ["./docker-entrypoint.sh"]
CMD ["dashboard"]
