"""
智能重命名界面功能完整性验证脚本

用途: 验证前端界面元素是否都有对应的函数实现
输入: 无
输出: 验证结果报告
副作用: 无
"""

import re
from typing import Dict, List, Set, Tuple

# ==================== 前端界面元素定义 ====================
FRONTEND_UI_ELEMENTS = {
    # 按钮点击事件
    "exportPreview": {
        "type": "button_click",
        "description": "导出预览按钮",
        "required": True
    },
    "refreshPreview": {
        "type": "button_click",
        "description": "重新分析按钮",
        "required": True
    },
    "confirmSelected": {
        "type": "button_click",
        "description": "批量确认按钮",
        "required": True
    },
    "editSelected": {
        "type": "button_click",
        "description": "批量编辑按钮",
        "required": True
    },
    # 输入框绑定
    "searchKeyword": {
        "type": "v_model",
        "description": "搜索关键词输入框",
        "required": True
    },
    "sortBy": {
        "type": "v_model",
        "description": "排序选择器",
        "required": True
    },
    # 已存在的函数（用于验证）
    "loadAlgorithms": {
        "type": "function",
        "description": "加载算法列表",
        "required": True
    },
    "loadNamingStandards": {
        "type": "function",
        "description": "加载命名标准",
        "required": True
    },
    "loadStatus": {
        "type": "function",
        "description": "加载服务状态",
        "required": True
    },
    "openPathSelector": {
        "type": "function",
        "description": "打开路径选择器",
        "required": True
    },
    "startAnalysis": {
        "type": "function",
        "description": "开始分析",
        "required": True
    },
    "handleSelectAll": {
        "type": "function",
        "description": "全选处理",
        "required": True
    },
    "getFileName": {
        "type": "function",
        "description": "获取文件名",
        "required": True
    },
    "getMediaTypeLabel": {
        "type": "function",
        "description": "获取媒体类型标签",
        "required": True
    },
    "getMediaTypeColor": {
        "type": "function",
        "description": "获取媒体类型颜色",
        "required": True
    },
    "getAlgorithmName": {
        "type": "function",
        "description": "获取算法名称",
        "required": True
    },
    "getAlgorithmShortName": {
        "type": "function",
        "description": "获取算法简称",
        "required": True
    },
    "getStandardName": {
        "type": "function",
        "description": "获取标准名称",
        "required": True
    },
    "getConfidenceClass": {
        "type": "function",
        "description": "获取置信度样式类",
        "required": True
    },
    "editItem": {
        "type": "function",
        "description": "编辑项目",
        "required": True
    },
    "saveItemEdit": {
        "type": "function",
        "description": "保存项目编辑",
        "required": True
    },
    "removeItem": {
        "type": "function",
        "description": "移除项目",
        "required": True
    },
    "saveSettings": {
        "type": "function",
        "description": "保存设置",
        "required": True
    },
    "executeRename": {
        "type": "function",
        "description": "执行重命名",
        "required": True
    },
    "resetWorkflow": {
        "type": "function",
        "description": "重置工作流",
        "required": True
    }
}

# ==================== 解析函数 ====================

def parse_vue_file(file_path: str) -> Tuple[Set[str], Set[str], Set[str]]:
    """
    解析 Vue 文件，提取定义的函数、变量和 ref/reactive
    
    返回:
        Tuple: (函数集合, 变量集合, ref/reactive 集合)
    """
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 提取 script 部分
    script_match = re.search(r'<script[^>]*>(.*?)</script>', content, re.DOTALL)
    if not script_match:
        return set(), set(), set()
    
    script_content = script_match.group(1)
    
    # 提取函数定义
    functions = set()
    function_pattern = r'const\s+(\w+)\s*=\s*(?:async\s*)?\([^)]*\)\s*=>'
    functions.update(re.findall(function_pattern, script_content))
    
    # 提取 ref 定义
    refs = set()
    ref_pattern = r'const\s+(\w+)\s*=\s*ref\('
    refs.update(re.findall(ref_pattern, script_content))
    
    # 提取 reactive 定义
    reactives = set()
    reactive_pattern = r'const\s+(\w+)\s*=\s*reactive\('
    reactives.update(re.findall(reactive_pattern, script_content))
    
    # 提取 computed 定义
    computeds = set()
    computed_pattern = r'const\s+(\w+)\s*=\s*computed\('
    computeds.update(re.findall(computed_pattern, script_content))
    
    # 合并所有变量
    variables = refs | reactives | computeds
    
    return functions, variables, refs

def verify_ui_elements(file_path: str) -> Dict[str, any]:
    """
    验证界面元素是否都有对应的实现
    
    返回:
        Dict: 验证结果
    """
    functions, variables, refs = parse_vue_file(file_path)
    
    results = {
        "missing_functions": [],
        "missing_variables": [],
        "missing_refs": [],
        "all_present": []
    }
    
    for element_name, element_info in FRONTEND_UI_ELEMENTS.items():
        element_type = element_info["type"]
        required = element_info["required"]
        
        found = False
        
        if element_type == "button_click":
            # 按钮点击事件需要函数
            if element_name in functions:
                found = True
        elif element_type == "v_model":
            # v-model 绑定需要 ref 或 reactive
            if element_name in variables:
                found = True
        elif element_type == "function":
            # 普通函数
            if element_name in functions:
                found = True
        
        if found:
            results["all_present"].append({
                "name": element_name,
                "type": element_type,
                "description": element_info["description"]
            })
        elif required:
            if element_type == "button_click" or element_type == "function":
                results["missing_functions"].append({
                    "name": element_name,
                    "type": element_type,
                    "description": element_info["description"]
                })
            elif element_type == "v_model":
                results["missing_variables"].append({
                    "name": element_name,
                    "type": element_type,
                    "description": element_info["description"]
                })
    
    return results

def generate_report(file_path: str) -> str:
    """
    生成验证报告
    
    返回:
        str: 格式化的报告文本
    """
    report = []
    report.append("=" * 80)
    report.append("智能重命名界面功能完整性验证报告")
    report.append("=" * 80)
    report.append("")
    
    # 验证界面元素
    report.append("## 1. 界面元素功能验证")
    report.append("-" * 80)
    results = verify_ui_elements(file_path)
    
    report.append(f"✅ 已正确实现: {len(results['all_present'])}")
    for item in results["all_present"]:
        report.append(f"   - {item['name']}: {item['description']} ({item['type']})")
    report.append("")
    
    if results["missing_functions"]:
        report.append(f"❌ 缺失的函数: {len(results['missing_functions'])}")
        for item in results["missing_functions"]:
            report.append(f"   - {item['name']}: {item['description']}")
        report.append("")
    
    if results["missing_variables"]:
        report.append(f"❌ 缺失的变量: {len(results['missing_variables'])}")
        for item in results["missing_variables"]:
            report.append(f"   - {item['name']}: {item['description']}")
        report.append("")
    
    # 总结
    report.append("## 2. 验证总结")
    report.append("-" * 80)
    total_issues = len(results["missing_functions"]) + len(results["missing_variables"])
    
    if total_issues == 0:
        report.append("✅ 所有界面元素功能完整，可以正常运行！")
    else:
        report.append(f"⚠️  发现 {total_issues} 个缺失的功能需要实现")
        report.append("")
        report.append("### 建议修复方案:")
        
        if results["missing_functions"]:
            report.append("#### 缺失函数实现:")
            for item in results["missing_functions"]:
                report.append(f"```javascript")
                report.append(f"const {item['name']} = () => {{")
                report.append(f"  // TODO: 实现 {item['description']}")
                report.append(f"  ElMessage.info('功能开发中')")
                report.append(f"}}")
                report.append(f"```")
                report.append("")
        
        if results["missing_variables"]:
            report.append("#### 缺失变量定义:")
            for item in results["missing_variables"]:
                report.append(f"```javascript")
                report.append(f"const {item['name']} = ref('')")
                report.append(f"```")
                report.append("")
    
    report.append("")
    report.append("=" * 80)
    
    return "\n".join(report)

if __name__ == "__main__":
    vue_file = "web/src/views/SmartRenameView.vue"
    print(generate_report(vue_file))
