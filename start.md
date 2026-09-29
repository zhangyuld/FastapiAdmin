# 启动服务步骤：

## mysql 启动

  运行 `net start MySQL84`
  提示服务已启动

## 手动启动docker

## 启动redis

  运行：
  `docker run --name redis-local -p 127.0.0.1:6379:6379 -v redis-data:/data -d redis redis-server --appendonly yes --requirepass 123456`

  - `--name redis-local`：容器名字，方便启停
  - `-p 127.0.0.1:6379:6379`：**只本机后端可以访问，外网无法连接，开发安全**
  - `-v redis-data:/data`：持久化，重启容器数据不丢
  - `--appendonly yes`：开启 AOF 持久化
  - `--requirepass 123456`：访问密码， 一次性
    - 如果未设置密码，可以进入redis-cli中设置
      `docker exec -it redis-local redis-cli`
      <!-- 设置密码 -->
      `CONFIG SET requirepass 123456`
      <!-- 验证 -->
      `AUTH 123456`

## 进入对应的后端文件夹中

  - 初始化：uv sync
  - 运行 `uv run main.py run --env=dev`

## 进入前端文件夹中

  ### web
  `cd ./frontend/web`
  - 初始化：`pnpm install`
  - 运行：`pnpm run dev`

  ### 移动端 (UniApp)
 ` cd ./frontend/app`
  `pnpm install`
  `pnpm run dev:h5`

  ### 文档网站 (VitePress)
  `cd ./frontend/docs`
  `pnpm install`
 ` pnpm run dev`