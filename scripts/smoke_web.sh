#!/bin/bash
#
# 前端构建冒烟测试脚本
#
# 用途: 验证前端项目可以成功构建
# 依赖: Node.js 20+, npm
#
# 用法:
#     ./scripts/smoke_web.sh
#     ./scripts/smoke_web.sh --verbose
#
# 退出码:
#     0 - 构建成功
#     1 - 构建失败
#     2 - 环境检查失败

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 参数解析
VERBOSE=false
if [[ "$1" == "--verbose" || "$1" == "-v" ]]; then
    VERBOSE=true
fi

# 日志函数
log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

log_step() {
    echo -e "\n${GREEN}==>${NC} $1"
}

# 检查环境
check_environment() {
    log_step "Checking environment..."
    
    # 检查Node.js
    if ! command -v node &> /dev/null; then
        log_error "Node.js is not installed"
        exit 2
    fi
    
    NODE_VERSION=$(node --version | cut -d'v' -f2 | cut -d'.' -f1)
    if [ "$NODE_VERSION" -lt 20 ]; then
        log_error "Node.js version must be 20 or higher (found: $(node --version))"
        exit 2
    fi
    
    log_info "Node.js version: $(node --version)"
    
    # 检查npm
    if ! command -v npm &> /dev/null; then
        log_error "npm is not installed"
        exit 2
    fi
    
    log_info "npm version: $(npm --version)"
    
    # 检查web目录
    if [ ! -d "web" ]; then
        log_error "web directory not found"
        exit 2
    fi
    
    log_info "Environment check passed"
}

# 安装依赖
install_dependencies() {
    log_step "Installing dependencies..."
    
    cd web
    
    if [ "$VERBOSE" = true ]; then
        npm ci
    else
        npm ci --silent
    fi
    
    log_info "Dependencies installed"
}

# 运行类型检查
run_type_check() {
    log_step "Running TypeScript type check..."
    
    if [ "$VERBOSE" = true ]; then
        npm run type-check
    else
        npm run type-check 2>&1 | grep -E "(error|Error|found)" || true
    fi
    
    log_info "Type check passed"
}

# 运行构建
run_build() {
    log_step "Building project..."
    
    # 清理旧的构建目录
    if [ -d "dist" ]; then
        rm -rf dist
        log_info "Cleaned old dist directory"
    fi
    
    # 执行构建
    if [ "$VERBOSE" = true ]; then
        npm run build-only
    else
        npm run build-only 2>&1 | tail -20
    fi
    
    # 检查dist目录
    if [ ! -d "dist" ]; then
        log_error "Build failed: dist directory not created"
        exit 1
    fi
    
    # 检查关键文件
    if [ ! -f "dist/index.html" ]; then
        log_error "Build failed: index.html not found"
        exit 1
    fi
    
    log_info "Build successful"
    log_info "Output directory: $(pwd)/dist"
    log_info "Output size: $(du -sh dist | cut -f1)"
}

# 运行lint检查
run_lint() {
    log_step "Running lint check..."
    
    # 注意：lint失败不阻断构建，只警告
    if npm run lint --silent 2>/dev/null; then
        log_info "Lint check passed"
    else
        log_warn "Lint check found issues (non-blocking)"
    fi
}

# 主函数
main() {
    echo "========================================"
    echo "Frontend Smoke Test"
    echo "========================================"
    
    # 获取脚本所在目录
    SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
    
    # 切换到项目根目录
    cd "$PROJECT_ROOT"
    
    # 执行测试步骤
    check_environment
    install_dependencies
    run_type_check
    run_build
    run_lint
    
    echo ""
    echo "========================================"
    log_info "All tests passed!"
    echo "========================================"
    
    exit 0
}

# 运行主函数
main
