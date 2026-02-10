#!/bin/bash
#
# Docker部署验收脚本（裁判化版本 + 企业级自动测试接管）
#
# 用途: 验证Docker部署的服务是否正常工作，并执行完整测试套件
# 执行环境: 远程服务器（通过GitHub Actions SSH调用）
#
# 验收等级:
#   - CRITICAL_FAIL: 必须阻断（exit 1）
#   - SOFT_FAIL: 可配置是否阻断（STRICT_MODE控制）
#   - INFO: 不影响验收
#
# 环境变量:
#   STRICT_MODE=true/false  (默认: true，CI中建议保持true)
#   SERVICE_PORT            (默认: 18000)
#   HEALTH_TIMEOUT          (默认: 30)
#   LOG_ERROR_THRESHOLD     (默认: 5)
#   DISK_WARNING_THRESHOLD  (默认: 80)
#   DISK_CRITICAL_THRESHOLD (默认: 90)
#   PYTEST_SKIP_THRESHOLD   (默认: 10)  skip数量超过此值 → SOFT_FAIL
#
# 退出码:
#   0 - 所有关键检查通过
#   1 - 有关键检查项失败（或 STRICT_MODE=true 时有SOFT_FAIL）

set -euo pipefail

# ============================================================================
# 配置区（可从环境变量覆盖）
# ============================================================================
STRICT_MODE="${STRICT_MODE:-true}"
SERVICE_PORT="${SERVICE_PORT:-18000}"
HEALTH_TIMEOUT="${HEALTH_TIMEOUT:-30}"
LOG_ERROR_THRESHOLD="${LOG_ERROR_THRESHOLD:-5}"
DISK_WARNING_THRESHOLD="${DISK_WARNING_THRESHOLD:-80}"
DISK_CRITICAL_THRESHOLD="${DISK_CRITICAL_THRESHOLD:-90}"
MEM_WARNING_THRESHOLD="${MEM_WARNING_THRESHOLD:-80}"
MEM_CRITICAL_THRESHOLD="${MEM_CRITICAL_THRESHOLD:-90}"
PYTEST_SKIP_THRESHOLD="${PYTEST_SKIP_THRESHOLD:-10}"

BASE_URL="http://127.0.0.1:${SERVICE_PORT}"

# ============================================================================
# 颜色定义（如果终端支持）
# ============================================================================
if [ -t 1 ]; then
    RED='\033[0;31m'
    GREEN='\033[0;32m'
    YELLOW='\033[1;33m'
    BLUE='\033[0;34m'
    NC='\033[0m'
else
    RED=''
    GREEN=''
    YELLOW=''
    BLUE=''
    NC=''
fi

# ============================================================================
# 计数器（按等级分类）
# ============================================================================
CRITICAL_FAILS=0
SOFT_FAILS=0
INFOS=0
WARNINGS=0

# ============================================================================
# 日志函数（带等级标记）
# ============================================================================
log_critical() {
    echo -e "${RED}[CRITICAL_FAIL]${NC} $1"
    ((CRITICAL_FAILS++))
}

log_soft() {
    echo -e "${YELLOW}[SOFT_FAIL]${NC} $1"
    ((SOFT_FAILS++))
}

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
    ((INFOS++))
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
    ((WARNINGS++))
}

log_step() {
    echo -e "\n${BLUE}==>${NC} $1"
}

log_rule() {
    echo -e "${BLUE}[RULE]${NC} $1"
}

log_test() {
    echo -e "${BLUE}[TEST]${NC} $1"
}

# ============================================================================
# 工具函数
# ============================================================================
check_command() {
    if command -v "$1" &> /dev/null; then
        return 0
    else
        return 1
    fi
}

# ============================================================================
# 检查1: Docker和Docker Compose可用性 [CRITICAL]
# 规则: Docker环境不可用 → CRITICAL_FAIL
# ============================================================================
check_docker() {
    log_step "Checking Docker environment..."
    log_rule "Docker/Compose/Daemon 任一不可用 → CRITICAL_FAIL"
    
    if check_command docker; then
        log_info "Docker is installed ($(docker --version))"
    else
        log_critical "Docker is not installed"
        return 1
    fi
    
    if docker compose version &> /dev/null; then
        log_info "Docker Compose is available"
    else
        log_critical "Docker Compose is not available"
        return 1
    fi
    
    if docker info &> /dev/null; then
        log_info "Docker daemon is running"
    else
        log_critical "Docker daemon is not running"
        return 1
    fi
}

# ============================================================================
# 检查2: 容器状态 [CRITICAL]
# 规则: 无运行容器 或 有unhealthy容器 → CRITICAL_FAIL
# ============================================================================
check_containers() {
    log_step "Checking container status..."
    log_rule "无运行容器 或 有unhealthy容器 → CRITICAL_FAIL"
    
    local containers
    containers=$(docker compose ps --format json 2>/dev/null || docker compose ps -q 2>/dev/null)
    
    if [ -z "$containers" ]; then
        log_critical "No containers found"
        return 1
    fi
    
    local running_count
    running_count=$(docker compose ps -q 2>/dev/null | wc -l)
    
    if [ "$running_count" -gt 0 ]; then
        log_info "Found ${running_count} running container(s)"
    else
        log_critical "No running containers found"
        return 1
    fi
    
    local unhealthy
    unhealthy=$(docker compose ps --format json 2>/dev/null | grep -c '"Health":"unhealthy"' || true)
    
    if [ "$unhealthy" -gt 0 ]; then
        log_critical "Found ${unhealthy} unhealthy container(s)"
    else
        log_info "All containers are healthy"
    fi
}

# ============================================================================
# 检查3: 端口监听 [CRITICAL]
# 规则: 服务端口未监听 → CRITICAL_FAIL
# ============================================================================
check_ports() {
    log_step "Checking port binding..."
    log_rule "端口 ${SERVICE_PORT} 未监听 → CRITICAL_FAIL"
    
    local port_listening=false
    
    if check_command ss; then
        if ss -tlnp | grep -q ":${SERVICE_PORT}"; then
            port_listening=true
        fi
    elif check_command netstat; then
        if netstat -tlnp 2>/dev/null | grep -q ":${SERVICE_PORT}"; then
            port_listening=true
        fi
    else
        log_warn "Cannot check ports (ss/netstat not available)"
        return 0
    fi
    
    if [ "$port_listening" = true ]; then
        log_info "Port ${SERVICE_PORT} is listening"
    else
        log_critical "Port ${SERVICE_PORT} is not listening"
        return 1
    fi
}

# ============================================================================
# 检查4: 健康检查端点 [CRITICAL]
# 规则: /health 不可达 → CRITICAL_FAIL
# ============================================================================
check_health_endpoint() {
    log_step "Checking health endpoint..."
    log_rule "/health 不可达 → CRITICAL_FAIL"
    
    local health_url="${BASE_URL}/health"
    local response=""
    
    if ! check_command curl; then
        log_critical "curl is not installed"
        return 1
    fi
    
    # 尝试获取健康状态
    for i in $(seq 1 "$HEALTH_TIMEOUT"); do
        if response=$(curl -fsS "${health_url}" 2>/dev/null); then
            break
        fi
        sleep 1
    done
    
    if [ -z "${response:-}" ]; then
        log_critical "Health endpoint not responding after ${HEALTH_TIMEOUT}s"
        return 1
    fi
    
    log_info "Health endpoint is accessible"
    
    # 检查响应内容（仅INFO级别）
    if echo "$response" | grep -q '"status"'; then
        local status
        status=$(echo "$response" | grep -o '"status":"[^"]*"' | cut -d'"' -f4)
        log_info "Health status: ${status}"
    fi
}

# ============================================================================
# 检查5: 根端点 [CRITICAL]
# 规则: 根端点不可达 → CRITICAL_FAIL
# ============================================================================
check_root_endpoint() {
    log_step "Checking root endpoint..."
    log_rule "/ 不可达 → CRITICAL_FAIL"
    
    local root_url="${BASE_URL}/"
    
    if curl -fsS "${root_url}" > /dev/null 2>&1; then
        log_info "Root endpoint is accessible"
    else
        log_critical "Root endpoint is not accessible"
        return 1
    fi
}

# ============================================================================
# 检查6: API端点 [CRITICAL]
# 规则: 任一 API 返回 500 → CRITICAL_FAIL
#       401/403 为预期行为 → INFO
# ============================================================================
check_api_endpoints() {
    log_step "Checking API endpoints..."
    log_rule "API 返回 500 → CRITICAL_FAIL"
    log_rule "API 返回 401/403 → INFO (预期行为)"
    
    local endpoints=(
        "/api/quark/files/0"
        "/api/strm/status"
        "/api/tasks"
    )
    
    local has_critical=false
    
    for endpoint in "${endpoints[@]}"; do
        local url="${BASE_URL}${endpoint}"
        local http_code
        
        http_code=$(curl -s -o /dev/null -w "%{http_code}" "${url}" 2>/dev/null || echo "000")
        
        case "$http_code" in
            200)
                log_info "API ${endpoint} OK (HTTP 200)"
                ;;
            401|403)
                log_info "API ${endpoint} requires auth (HTTP ${http_code})"
                ;;
            500)
                log_critical "API ${endpoint} returns server error (HTTP 500)"
                has_critical=true
                ;;
            000)
                log_warn "API ${endpoint} not responding"
                ;;
            *)
                log_warn "API ${endpoint} returns HTTP ${http_code}"
                ;;
        esac
    done
    
    if [ "$has_critical" = true ]; then
        return 1
    fi
}

# ============================================================================
# 检查7: 静态资源 [SOFT]
# 规则: 前端静态资源全部不可达 → SOFT_FAIL
# ============================================================================
check_static_files() {
    log_step "Checking static files..."
    log_rule "静态资源全部不可达 → SOFT_FAIL"
    
    local static_urls=(
        "/index.html"
        "/favicon.ico"
    )
    
    local accessible_count=0
    local total_count=${#static_urls[@]}
    
    for url_path in "${static_urls[@]}"; do
        local url="${BASE_URL}${url_path}"
        
        if curl -fsS -o /dev/null "${url}" 2>/dev/null; then
            log_info "Static file ${url_path} is accessible"
            ((accessible_count++))
        else
            log_warn "Static file ${url_path} not accessible"
        fi
    done
    
    # 全部不可达 → SOFT_FAIL
    if [ $accessible_count -eq 0 ] && [ $total_count -gt 0 ]; then
        log_soft "All static files are inaccessible"
    fi
}

# ============================================================================
# 检查8: 日志检查 [CRITICAL]
# 规则: 日志中 error/exception/fatal/traceback ≥ N → CRITICAL_FAIL
# ============================================================================
check_logs() {
    log_step "Checking container logs for errors..."
    log_rule "日志错误数 ≥ ${LOG_ERROR_THRESHOLD} → CRITICAL_FAIL"
    
    local error_count
    error_count=$(docker compose logs --no-color 2>&1 | grep -ciE "(error|exception|fatal|traceback)" || true)
    
    if [ "$error_count" -eq 0 ]; then
        log_info "No errors found in container logs"
    elif [ "$error_count" -lt "$LOG_ERROR_THRESHOLD" ]; then
        log_warn "Found ${error_count} potential errors in logs (below threshold ${LOG_ERROR_THRESHOLD})"
    else
        log_critical "Found ${error_count} errors in logs (threshold: ${LOG_ERROR_THRESHOLD})"
        return 1
    fi
}

# ============================================================================
# 检查9: 资源使用 [SOFT]
# 规则: 磁盘/内存超阈值 → SOFT_FAIL
# ============================================================================
check_resources() {
    log_step "Checking system resources..."
    log_rule "磁盘/内存超阈值 → SOFT_FAIL"
    
    local has_soft_fail=false
    
    # 磁盘空间
    if check_command df; then
        local disk_usage
        disk_usage=$(df -h . | awk 'NR==2 {print $5}' | tr -d '%')
        
        if [ "$disk_usage" -ge "$DISK_CRITICAL_THRESHOLD" ]; then
            log_soft "Disk usage: ${disk_usage}% (critical, threshold: ${DISK_CRITICAL_THRESHOLD}%)"
            has_soft_fail=true
        elif [ "$disk_usage" -ge "$DISK_WARNING_THRESHOLD" ]; then
            log_soft "Disk usage: ${disk_usage}% (high, threshold: ${DISK_WARNING_THRESHOLD}%)"
            has_soft_fail=true
        else
            log_info "Disk usage: ${disk_usage}%"
        fi
    fi
    
    # 内存使用
    if check_command free; then
        local mem_usage
        mem_usage=$(free | awk 'NR==2{printf "%.0f", $3*100/$2}')
        
        if [ "$mem_usage" -ge "$MEM_CRITICAL_THRESHOLD" ]; then
            log_soft "Memory usage: ${mem_usage}% (critical, threshold: ${MEM_CRITICAL_THRESHOLD}%)"
            has_soft_fail=true
        elif [ "$mem_usage" -ge "$MEM_WARNING_THRESHOLD" ]; then
            log_soft "Memory usage: ${mem_usage}% (high, threshold: ${MEM_WARNING_THRESHOLD}%)"
            has_soft_fail=true
        else
            log_info "Memory usage: ${mem_usage}%"
        fi
    fi
    
    if [ "$has_soft_fail" = true ]; then
        return 1
    fi
}

# ============================================================================
# 测试阶段 A: 容器内执行 pytest [CRITICAL]
# 规则: pytest 失败 → CRITICAL_FAIL
#       测试未运行 → CRITICAL_FAIL
#       skip数量异常过多 → SOFT_FAIL
# ============================================================================
run_pytest_in_container() {
    log_step "Running pytest inside container..."
    log_rule "pytest 失败 → CRITICAL_FAIL"
    log_rule "测试未运行 → CRITICAL_FAIL"
    log_rule "skip数量 ≥ ${PYTEST_SKIP_THRESHOLD} → SOFT_FAIL"
    
    # 获取容器名称
    local container_name
    container_name=$(docker compose ps -q | head -1)
    
    if [ -z "$container_name" ]; then
        log_critical "Cannot find running container for pytest"
        return 1
    fi
    
    log_test "Target container: ${container_name}"
    
    # 检查容器内是否有pytest和测试文件
    local has_pytest
    has_pytest=$(docker exec "$container_name" bash -c "command -v pytest" 2>/dev/null || echo "")
    
    if [ -z "$has_pytest" ]; then
        log_critical "pytest not found in container"
        return 1
    fi
    
    # 检查测试目录是否存在
    local has_tests
    has_tests=$(docker exec "$container_name" bash -c "test -d tests && echo 'yes' || echo 'no'" 2>/dev/null)
    
    if [ "$has_tests" != "yes" ]; then
        log_critical "tests/ directory not found in container"
        return 1
    fi
    
    # 执行pytest
    log_test "Executing: pytest tests/ -v --tb=short"
    
    local pytest_output
    local pytest_exit_code
    
    pytest_output=$(docker exec "$container_name" bash -c "cd /app && pytest tests/ -v --tb=short 2>&1" || true)
    pytest_exit_code=$?
    
    # 输出pytest结果
    echo "$pytest_output"
    
    # 检查是否实际运行了测试
    local test_count
    test_count=$(echo "$pytest_output" | grep -oP '\d+ passed' | grep -oP '\d+' || echo "0")
    
    if [ "$test_count" = "0" ] && [ "$pytest_exit_code" -ne 0 ]; then
        log_critical "pytest did not run any tests or failed to execute"
        return 1
    fi
    
    # 统计skip数量
    local skip_count
    skip_count=$(echo "$pytest_output" | grep -oP '\d+ skipped' | grep -oP '\d+' || echo "0")
    
    log_test "Test results: passed=${test_count}, skipped=${skip_count}"
    
    # 判定结果
    if [ "$pytest_exit_code" -ne 0 ]; then
        log_critical "pytest failed with exit code ${pytest_exit_code}"
        return 1
    fi
    
    # 检查skip数量是否异常
    if [ "$skip_count" -ge "$PYTEST_SKIP_THRESHOLD" ]; then
        log_soft "Too many skipped tests (${skip_count} >= ${PYTEST_SKIP_THRESHOLD})"
    else
        log_info "pytest passed (${test_count} tests, ${skip_count} skipped)"
    fi
}

# ============================================================================
# 测试阶段 B: 容器内执行 smoke_api.py [CRITICAL]
# 规则: smoke_api 失败 → CRITICAL_FAIL
#       测试未运行 → CRITICAL_FAIL
# ============================================================================
run_smoke_api_in_container() {
    log_step "Running smoke_api.py inside container..."
    log_rule "smoke_api 失败 → CRITICAL_FAIL"
    log_rule "测试未运行 → CRITICAL_FAIL"
    
    # 获取容器名称
    local container_name
    container_name=$(docker compose ps -q | head -1)
    
    if [ -z "$container_name" ]; then
        log_critical "Cannot find running container for smoke_api"
        return 1
    fi
    
    log_test "Target container: ${container_name}"
    
    # 检查脚本是否存在
    local has_script
    has_script=$(docker exec "$container_name" bash -c "test -f scripts/smoke_api.py && echo 'yes' || echo 'no'" 2>/dev/null)
    
    if [ "$has_script" != "yes" ]; then
        log_critical "scripts/smoke_api.py not found in container"
        return 1
    fi
    
    # 检查依赖
    local has_httpx
    has_httpx=$(docker exec "$container_name" bash -c "python -c 'import httpx' 2>/dev/null && echo 'yes' || echo 'no'")
    
    if [ "$has_httpx" != "yes" ]; then
        log_critical "httpx not installed in container"
        return 1
    fi
    
    # 执行smoke_api（指向容器内服务）
    log_test "Executing: python scripts/smoke_api.py --base-url http://127.0.0.1:${SERVICE_PORT}"
    
    local smoke_output
    local smoke_exit_code
    
    smoke_output=$(docker exec "$container_name" bash -c "cd /app && python scripts/smoke_api.py --base-url http://127.0.0.1:${SERVICE_PORT} 2>&1" || true)
    smoke_exit_code=$?
    
    # 输出结果
    echo "$smoke_output"
    
    # 检查是否实际运行了测试
    if ! echo "$smoke_output" | grep -q "API Smoke Tests"; then
        log_critical "smoke_api.py did not run properly"
        return 1
    fi
    
    # 判定结果
    if [ "$smoke_exit_code" -ne 0 ]; then
        log_critical "smoke_api.py failed with exit code ${smoke_exit_code}"
        return 1
    fi
    
    log_info "smoke_api.py passed"
}

# ============================================================================
# 测试阶段 C: 容器外执行 smoke_web.sh [CRITICAL]
# 规则: smoke_web 构建失败 → CRITICAL_FAIL
#       测试未运行 → CRITICAL_FAIL
# ============================================================================
run_smoke_web_outside_container() {
    log_step "Running smoke_web.sh outside container..."
    log_rule "smoke_web 构建失败 → CRITICAL_FAIL"
    log_rule "测试未运行 → CRITICAL_FAIL"
    
    # 检查脚本是否存在
    if [ ! -f "scripts/smoke_web.sh" ]; then
        log_critical "scripts/smoke_web.sh not found"
        return 1
    fi
    
    # 检查web目录是否存在
    if [ ! -d "web" ]; then
        log_critical "web/ directory not found"
        return 1
    fi
    
    # 检查Node.js环境
    if ! check_command node; then
        log_critical "Node.js not installed on host"
        return 1
    fi
    
    log_test "Node.js version: $(node --version)"
    
    # 执行smoke_web
    log_test "Executing: bash scripts/smoke_web.sh"
    
    local smoke_output
    local smoke_exit_code
    
    smoke_output=$(bash scripts/smoke_web.sh 2>&1) || true
    smoke_exit_code=$?
    
    # 输出结果
    echo "$smoke_output"
    
    # 检查是否实际运行了测试
    if ! echo "$smoke_output" | grep -q "Frontend Smoke Test"; then
        log_critical "smoke_web.sh did not run properly"
        return 1
    fi
    
    # 判定结果
    if [ "$smoke_exit_code" -ne 0 ]; then
        log_critical "smoke_web.sh failed with exit code ${smoke_exit_code}"
        return 1
    fi
    
    log_info "smoke_web.sh passed"
}

# ============================================================================
# 判定函数
# ============================================================================
make_judgment() {
    echo ""
    echo "========================================"
    echo "Verification Summary"
    echo "========================================"
    echo -e "${GREEN}INFO:        ${INFOS}${NC}"
    echo -e "${YELLOW}WARN:        ${WARNINGS}${NC}"
    echo -e "${YELLOW}SOFT_FAIL:   ${SOFT_FAILS}${NC}"
    echo -e "${RED}CRITICAL_FAIL: ${CRITICAL_FAILS}${NC}"
    echo "========================================"
    echo "STRICT_MODE: ${STRICT_MODE}"
    echo "========================================"
    
    # 判定逻辑
    if [ $CRITICAL_FAILS -gt 0 ]; then
        echo -e "${RED}JUDGMENT: REJECTED (Critical failures detected)${NC}"
        echo "Reason: ${CRITICAL_FAILS} critical check(s) failed"
        return 1
    fi
    
    if [ $SOFT_FAILS -gt 0 ]; then
        if [ "$STRICT_MODE" = "true" ]; then
            echo -e "${YELLOW}JUDGMENT: REJECTED (Strict mode, soft failures not allowed)${NC}"
            echo "Reason: ${SOFT_FAILS} soft check(s) failed"
            return 1
        else
            echo -e "${YELLOW}JUDGMENT: ACCEPTED WITH WARNINGS (Non-strict mode)${NC}"
            echo "Warning: ${SOFT_FAILS} soft check(s) failed but ignored in non-strict mode"
            return 0
        fi
    fi
    
    echo -e "${GREEN}JUDGMENT: PASSED (All checks passed)${NC}"
    return 0
}

# ============================================================================
# 主函数
# ============================================================================
main() {
    echo "========================================"
    echo "Docker Deployment Verification (Judge)"
    echo "========================================"
    echo "Base URL: ${BASE_URL}"
    echo "STRICT_MODE: ${STRICT_MODE}"
    echo "Started at: $(date -u +"%Y-%m-%d %H:%M:%S UTC")"
    echo "========================================"
    
    # 检查是否在正确的目录
    if [ ! -f "docker-compose.yml" ] && [ ! -f "docker-compose.yaml" ]; then
        echo -e "${RED}[CRITICAL_FAIL]${NC} docker-compose.yml not found in current directory"
        echo "Current directory: $(pwd)"
        exit 1
    fi
    
    # 执行所有检查（使用子shell避免set -e导致提前退出）
    (
        check_docker
    ) || true
    
    (
        check_containers
    ) || true
    
    (
        check_ports
    ) || true
    
    (
        check_health_endpoint
    ) || true
    
    (
        check_root_endpoint
    ) || true
    
    (
        check_api_endpoints
    ) || true
    
    (
        check_static_files
    ) || true
    
    (
        check_logs
    ) || true
    
    (
        check_resources
    ) || true
    
    # 执行测试阶段（顺序固定）
    (
        run_pytest_in_container
    ) || true
    
    (
        run_smoke_api_in_container
    ) || true
    
    (
        run_smoke_web_outside_container
    ) || true
    
    # 最终判定
    make_judgment
    exit $?
}

# 执行主函数
main
