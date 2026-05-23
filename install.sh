#!/bin/bash

# mp 安装脚本
# 支持 Linux/macOS

set -e

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

print_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

print_success() {
    echo -e "${GREEN}✓${NC} $1"
}

print_banner() {
    echo -e "${BLUE}"
    cat << "EOF"
    ╔═══════════════════════════════════════════╗
    ║     mp - Terminal Audio Player            ║
    ║     轻量级终端音频播放器                   ║
    ╚═══════════════════════════════════════════╝
EOF
    echo -e "${NC}"
}

# 检测系统
detect_os() {
    case "$(uname -s)" in
        Darwin*)    echo "macos";;
        Linux*)     echo "linux";;
        CYGWIN*|MINGW*|MSYS*) echo "windows";;
        *)          echo "unknown";;
    esac
}

OS=$(detect_os)
print_info "检测到系统: $OS"

# 获取脚本所在目录
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MP_PY="$SCRIPT_DIR/mp.py"

# 设置Python命令
PYTHON_CMD="python3"
if ! command -v $PYTHON_CMD &> /dev/null; then
    if command -v python &> /dev/null; then
        PYTHON_CMD="python"
    else
        print_error "未找到Python，请先安装Python 3.7+"
        exit 1
    fi
fi

# 检查Python版本
PYTHON_VERSION=$($PYTHON_CMD -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
PYTHON_MAJOR=$($PYTHON_CMD -c 'import sys; print(sys.version_info.major)')
PYTHON_MINOR=$($PYTHON_CMD -c 'import sys; print(sys.version_info.minor)')

print_info "Python版本: $PYTHON_VERSION"

if [ "$PYTHON_MAJOR" -lt 3 ] || ([ "$PYTHON_MAJOR" -eq 3 ] && [ "$PYTHON_MINOR" -lt 7 ]); then
    print_error "需要Python 3.7或更高版本"
    exit 1
fi

# 确保mp.py可执行
if [ -f "$MP_PY" ]; then
    chmod +x "$MP_PY"
else
    print_error "找不到 mp.py 文件"
    exit 1
fi

# 安装ffmpeg
install_ffmpeg() {
    if command -v ffmpeg &> /dev/null; then
        print_success "ffmpeg已安装"
        return
    fi
    
    print_warn "未检测到ffmpeg，正在自动安装..."
    
    case "$OS" in
        macos)
            if command -v brew &> /dev/null; then
                print_info "使用Homebrew安装ffmpeg..."
                brew install ffmpeg
                print_success "ffmpeg安装完成"
            else
                print_error "请先安装Homebrew: https://brew.sh"
                exit 1
            fi
            ;;
        linux)
            if command -v apt &> /dev/null; then
                print_info "使用apt安装ffmpeg..."
                sudo apt update && sudo apt install -y ffmpeg
                print_success "ffmpeg安装完成"
            elif command -v yum &> /dev/null; then
                print_info "使用yum安装ffmpeg..."
                sudo yum install -y ffmpeg
                print_success "ffmpeg安装完成"
            elif command -v dnf &> /dev/null; then
                print_info "使用dnf安装ffmpeg..."
                sudo dnf install -y ffmpeg
                print_success "ffmpeg安装完成"
            elif command -v pacman &> /dev/null; then
                print_info "使用pacman安装ffmpeg..."
                sudo pacman -S --noconfirm ffmpeg
                print_success "ffmpeg安装完成"
            elif command -v zypper &> /dev/null; then
                print_info "使用zypper安装ffmpeg..."
                sudo zypper install -y ffmpeg
                print_success "ffmpeg安装完成"
            else
                print_error "无法自动安装ffmpeg，请手动安装"
                exit 1
            fi
            ;;
        windows)
            print_error "Windows请使用install.ps1"
            exit 1
            ;;
    esac
}

# 安装系统依赖（仅Linux）
install_system_deps() {
    if [[ "$OS" == "linux" ]]; then
        print_info "安装系统依赖（SDL2）..."
        
        if command -v apt &> /dev/null; then
            sudo apt install -y libsdl2-2.0-0 libsdl2-mixer-2.0-0 || true
            print_success "SDL2安装完成"
        elif command -v pacman &> /dev/null; then
            sudo pacman -S --noconfirm sdl2 sdl2_mixer || true
            print_success "SDL2安装完成"
        elif command -v dnf &> /dev/null; then
            sudo dnf install -y SDL2 SDL2_mixer || true
            print_success "SDL2安装完成"
        elif command -v yum &> /dev/null; then
            sudo yum install -y SDL2 SDL2_mixer || true
            print_success "SDL2安装完成"
        else
            print_warn "无法自动安装SDL2，如果播放失败请手动安装"
        fi
    fi
}

# 创建符号链接到PATH
install_to_path() {
    local install_path=""
    
    # 查找PATH中的目录
    if [[ "$OS" == "windows" ]]; then
        if [[ -d "$HOME/.local/bin" ]]; then
            install_path="$HOME/.local/bin"
        elif [[ -d "$HOME/bin" ]]; then
            install_path="$HOME/bin"
        else
            mkdir -p "$HOME/.local/bin"
            install_path="$HOME/.local/bin"
        fi
    else
        # Unix-like系统
        if [[ -d "$HOME/.local/bin" ]]; then
            install_path="$HOME/.local/bin"
        elif [[ -d "$HOME/bin" ]]; then
            install_path="$HOME/bin"
        else
            mkdir -p "$HOME/.local/bin"
            install_path="$HOME/.local/bin"
        fi
    fi
    
    # 创建包装脚本
    local wrapper="$install_path/mp"
    cat > "$wrapper" << 'EOF'
#!/usr/bin/env bash
# mp 包装脚本 - Terminal Audio Player 启动器

# 查找真实的mp.py位置
REAL_MP_PY=""

# 优先查找用户安装目录
if [[ -f "$HOME/.local/share/mp/mp.py" ]]; then
    REAL_MP_PY="$HOME/.local/share/mp/mp.py"
fi

# 尝试系统安装目录
if [[ -z "$REAL_MP_PY" && -f "/usr/local/share/mp/mp.py" ]]; then
    REAL_MP_PY="/usr/local/share/mp/mp.py"
fi

# 尝试脚本所在目录
if [[ -z "$REAL_MP_PY" ]]; then
    SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    if [[ -f "$SCRIPT_DIR/../mp/mp.py" ]]; then
        REAL_MP_PY="$SCRIPT_DIR/../mp/mp.py"
    elif [[ -f "$SCRIPT_DIR/mp.py" ]]; then
        REAL_MP_PY="$SCRIPT_DIR/mp.py"
    fi
fi

# 最后尝试当前目录
if [[ -z "$REAL_MP_PY" && -f "$PWD/mp.py" ]]; then
    REAL_MP_PY="$PWD/mp.py"
fi

if [[ -z "$REAL_MP_PY" ]]; then
    echo "错误: 找不到 mp.py"
    echo "请重新运行安装脚本"
    exit 1
fi

# 运行播放器，传递所有参数
exec python3 "$REAL_MP_PY" "$@"
EOF
    
    chmod +x "$wrapper"
    print_success "已安装到: $wrapper"
    
    # 复制mp.py到共享位置
    mkdir -p "$HOME/.local/share/mp"
    cp "$MP_PY" "$HOME/.local/share/mp/mp.py"
    chmod +x "$HOME/.local/share/mp/mp.py"
    
    # 添加到PATH（如果需要）
    if [[ ":$PATH:" != *":$install_path:"* ]]; then
        print_warn "请将以下行添加到你的shell配置文件（~/.bashrc, ~/.zshrc等）:"
        echo "  export PATH=\"\$HOME/.local/bin:\$PATH\""
        echo ""
        print_info "或者运行以下命令立即生效:"
        echo "  export PATH=\"\$HOME/.local/bin:\$PATH\""
    fi
}

# 安装自动补全
install_completions() {
    local current_shell=$(basename "$SHELL")
    
    case "$current_shell" in
        bash)
            local completion_dir="$HOME/.bash_completion.d"
            mkdir -p "$completion_dir"
            cat > "$completion_dir/mp" << 'EOF'
_mp_completion() {
    local cur="${COMP_WORDS[COMP_CWORD]}"
    local prev="${COMP_WORDS[COMP_CWORD-1]}"
    
    # 选项补全
    if [[ "$cur" == -* ]]; then
        COMPREPLY=($(compgen -W "-h --help" -- "$cur"))
        return 0
    fi
    
    # 文件补全（音频文件）
    local files=$(compgen -f -- "$cur" | grep -E '\.(mp3|wav|ogg|m4a|flac|aac|opus|mp4|m4b)$' || true)
    COMPREPLY=($(compgen -W "$files" -- "$cur"))
}
complete -F _mp_completion mp
EOF
            if ! grep -q "source $completion_dir/mp" "$HOME/.bashrc" 2>/dev/null; then
                echo "source $completion_dir/mp" >> "$HOME/.bashrc"
                print_success "已添加bash补全"
            fi
            ;;
        zsh)
            local completion_dir="$HOME/.zsh/completions"
            mkdir -p "$completion_dir"
            cat > "$completion_dir/_mp" << 'EOF'
#compdef mp
_mp() {
    _arguments \
        '-h[显示帮助信息]' \
        '--help[显示帮助信息]' \
        '*:audio file:_files -g "*.mp3 *.wav *.ogg *.m4a *.flac *.aac *.opus"'
}
compdef _mp mp
EOF
            if ! grep -q "fpath=($completion_dir" "$HOME/.zshrc" 2>/dev/null; then
                echo "fpath=($completion_dir \$fpath)" >> "$HOME/.zshrc"
                echo "autoload -Uz compinit && compinit" >> "$HOME/.zshrc"
                print_success "已添加zsh补全"
            fi
            ;;
        fish)
            local completion_dir="$HOME/.config/fish/completions"
            mkdir -p "$completion_dir"
            cat > "$completion_dir/mp.fish" << 'EOF'
complete -c mp -s h -l help -d "显示帮助信息"
complete -c mp -f -a "(__fish_complete_suffix mp3 wav ogg m4a flac aac opus)"
EOF
            print_success "已添加fish补全"
            ;;
    esac
}

# 卸载功能
uninstall() {
    print_warn "开始卸载 mp..."
    
    rm -f "$HOME/.local/bin/mp"
    rm -rf "$HOME/.local/share/mp"
    rm -f "$HOME/.bash_completion.d/mp"
    rm -f "$HOME/.zsh/completions/_mp"
    rm -f "$HOME/.config/fish/completions/mp.fish"
    
    print_success "卸载完成"
}

# 显示帮助
show_help() {
    cat << 'EOF'
╔═══════════════════════════════════════════════════════════════╗
║                    mp - Terminal Audio Player                 ║
╚═══════════════════════════════════════════════════════════════╝

一个轻量级的终端音频播放器，支持多种音频格式。

用法:
    mp [选项] <音频文件>

选项:
    -h, --help          显示此帮助信息

参数:
    <音频文件>          要播放的音频文件路径

支持格式:
    MP3, WAV, OGG, M4A, FLAC, AAC, OPUS 等

示例:
    mp song.mp3                         # 播放音乐
    mp "music/歌曲.flac"                # 支持带空格的路径

播放控制:
    空格键              暂停/继续
    ← 左箭头            后退10秒
    → 右箭头            前进10秒
    q 或 Ctrl+C         退出播放

提示:
    • 播放器会自动安装ffmpeg和pygame依赖
    • 支持带空格的路径，请使用引号括起来
EOF
}

# 主安装流程
main() {
    print_banner
    
    if [[ "$1" == "--uninstall" ]] || [[ "$1" == "-u" ]]; then
        uninstall
        exit 0
    fi
    
    print_info "开始安装 mp 音频播放器..."
    
    install_ffmpeg
    install_system_deps
    
    print_info "安装Python依赖..."
    
    PIP_ARGS=""
    if [[ "$OS" == "linux" ]]; then
        IN_VENV=$($PYTHON_CMD -c 'import sys; print(hasattr(sys, "real_prefix") or (hasattr(sys, "base_prefix") and sys.base_prefix != sys.prefix))')
        if [[ "$IN_VENV" == "False" ]]; then
            PIP_ARGS="--break-system-packages"
        fi
    fi
    
    $PYTHON_CMD -m pip install $PIP_ARGS pygame || {
        $PYTHON_CMD -m pip install --user pygame || {
            print_error "pygame安装失败，请手动安装"
            exit 1
        }
    }
    
    print_success "pygame安装完成"
    
    install_to_path
    install_completions
    
    clear
    print_banner
    print_success "安装完成！"
    echo ""
    print_info "使用方法: mp <音频文件>"
    echo ""
    echo -e "${BLUE}示例:${NC}"
    echo "  mp song.mp3          # 播放音乐"
    echo "  mp --help            # 显示帮助"
    echo ""
    echo -e "${BLUE}播放控制:${NC}"
    echo "  空格键    暂停/继续"
    echo "  ←/→ 键    后退/前进10秒"
    echo "  q/Ctrl+C  退出"
    echo ""
    
    print_success "现在可以在任何地方使用 'mp' 命令了！"
}

main "$@"
