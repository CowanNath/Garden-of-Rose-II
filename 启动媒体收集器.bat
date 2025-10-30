@echo off
chcp 65001 >nul
title 媒体收集器 - 无缓存模式

echo ========================================
echo       媒体收集器 - 无缓存模式
echo ========================================
echo.

REM 切换到脚本所在目录
cd /d "%~dp0"

REM 使用 -B 参数强制禁用字节码缓存
echo 正在启动媒体收集器 (使用 -B 参数禁用缓存)...
echo.

python -B media_collector.py %*

REM 检查并清理可能生成的缓存
if exist "__pycache__" (
    echo.
    echo 检测到缓存文件，正在清理...
    rmdir /s /q "__pycache__"
    echo 已清理 __pycache__ 文件夹
)

REM 递归清理子目录中的缓存
for /d /r . %%d in (__pycache__) do (
    if exist "%%d" (
        echo 清理: %%d
        rmdir /s /q "%%d"
    )
)

echo.
echo 操作完成！
pause