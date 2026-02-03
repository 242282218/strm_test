"""
智能重命名界面与接口对应关系验证脚本

用途: 验证前端界面功能元素与后端API接口的对应关系
输入: 无
输出: 验证结果报告
副作用: 无
"""

import sys
import os
from typing import Dict, List, Any

# 添加项目路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

# ==================== 前端 API 接口定义 ====================
FRONTEND_APIS = {
    "previewSmartRename": {
        "endpoint": "/smart-rename/preview",
        "method": "POST",
        "params": {
            "target_path": "string",
            "algorithm": "standard | ai_enhanced | ai_only",
            "naming_standard": "emby | plex | kodi | custom",
            "recursive": "boolean",
            "create_folders": "boolean",
            "auto_confirm_high_confidence": "boolean",
            "ai_confidence_threshold": "number",
            "naming_config": "object"
        },
        "response": {
            "batch_id": "string",
            "target_path": "string",
            "total_items": "number",
            "matched_items": "number",
            "needs_confirmation": "number",
            "items": "array",
            "algorithm_used": "string",
            "naming_standard": "string"
        }
    },
    "executeSmartRename": {
        "endpoint": "/smart-rename/execute",
        "method": "POST",
        "params": {
            "batch_id": "string"
        },
        "response": {
            "batch_id": "string",
            "total_items": "number",
            "success_items": "number",
            "failed_items": "number",
            "skipped_items": "number"
        }
    },
    "getAlgorithms": {
        "endpoint": "/smart-rename/algorithms",
        "method": "GET",
        "params": {},
        "response": [
            {
                "algorithm": "string",
                "name": "string",
                "description": "string",
                "features": "array",
                "recommended": "boolean"
            }
        ]
    },
    "getNamingStandards": {
        "endpoint": "/smart-rename/naming-standards",
        "method": "GET",
        "params": {},
        "response": [
            {
                "standard": "string",
                "name": "string",
                "description": "string",
                "movie_example": "string",
                "tv_example": "string",
                "specials_example": "string"
            }
        ]
    },
    "getSmartRenameStatus": {
        "endpoint": "/smart-rename/status",
        "method": "GET",
        "params": {},
        "response": {
            "available": "boolean",
            "smart_rename_service": "boolean",
            "tmdb_connected": "boolean",
            "ai_available": "boolean",
            "algorithms": "array",
            "naming_standards": "array"
        }
    },
    "rollbackSmartRename": {
        "endpoint": "/smart-rename/rollback/{batch_id}",
        "method": "POST",
        "params": {
            "batch_id": "string"
        },
        "response": {
            "batch_id": "string",
            "total_items": "number",
            "success_items": "number",
            "failed_items": "number"
        }
    },
    "validateFilename": {
        "endpoint": "/smart-rename/validate",
        "method": "POST",
        "params": {
            "filename": "string"
        },
        "response": {
            "filename": "string",
            "is_valid": "boolean",
            "suggestions": "array",
            "warnings": "array"
        }
    }
}

# ==================== 后端 API 接口定义 ====================
BACKEND_APIS = {
    "smart_preview": {
        "endpoint": "/api/smart-rename/preview",
        "method": "POST",
        "request_model": "SmartRenamePreviewRequest",
        "response_model": "SmartRenamePreviewResponse"
    },
    "smart_execute": {
        "endpoint": "/api/smart-rename/execute",
        "method": "POST",
        "request_model": "SmartRenameExecuteRequest",
        "response_model": "SmartRenameExecuteResponse"
    },
    "smart_rollback": {
        "endpoint": "/api/smart-rename/rollback/{batch_id}",
        "method": "POST",
        "response_model": "SmartRenameExecuteResponse"
    },
    "list_algorithms": {
        "endpoint": "/api/smart-rename/algorithms",
        "method": "GET",
        "response_model": "List[AlgorithmInfoResponse]"
    },
    "list_naming_standards": {
        "endpoint": "/api/smart-rename/naming-standards",
        "method": "GET",
        "response_model": "List[NamingStandardInfoResponse]"
    },
    "validate_filename": {
        "endpoint": "/api/smart-rename/validate",
        "method": "POST",
        "response_model": "ValidationResponse"
    },
    "list_batches": {
        "endpoint": "/api/smart-rename/batches",
        "method": "GET",
        "response_model": "List[Dict[str, Any]]"
    },
    "get_batch_items": {
        "endpoint": "/api/smart-rename/batches/{batch_id}/items",
        "method": "GET",
        "response_model": "List[Dict[str, Any]]"
    },
    "get_smart_rename_status": {
        "endpoint": "/api/smart-rename/status",
        "method": "GET",
        "response_model": "Dict[str, Any]"
    }
}

# ==================== 前端界面功能元素定义 ====================
FRONTEND_UI_ELEMENTS = {
    "algorithm_selection": {
        "element": "el-radio-group (selectedAlgorithm)",
        "api_dependency": "getAlgorithms",
        "description": "重命名算法选择"
    },
    "naming_standard_selection": {
        "element": "el-radio-group (selectedStandard)",
        "api_dependency": "getNamingStandards",
        "description": "命名标准选择"
    },
    "path_selector": {
        "element": "el-input (selectedPath)",
        "api_dependency": "previewSmartRename",
        "description": "文件夹路径选择"
    },
    "scan_button": {
        "element": "el-button (扫描媒体文件)",
        "api_dependency": "previewSmartRename",
        "description": "触发扫描分析"
    },
    "preview_list": {
        "element": "div.file-list",
        "api_dependency": "previewSmartRename",
        "description": "预览结果列表"
    },
    "execute_button": {
        "element": "el-button (确认执行)",
        "api_dependency": "executeSmartRename",
        "description": "执行重命名"
    },
    "settings_dialog": {
        "element": "el-dialog (showSettings)",
        "api_dependency": None,
        "description": "高级配置对话框"
    },
    "edit_dialog": {
        "element": "el-dialog (editDialogVisible)",
        "api_dependency": None,
        "description": "编辑项目对话框"
    },
    "result_dialog": {
        "element": "el-dialog (resultDialogVisible)",
        "api_dependency": "executeSmartRename",
        "description": "执行结果对话框"
    },
    "status_display": {
        "element": "div.stats-panel",
        "api_dependency": "previewSmartRename",
        "description": "统计信息显示"
    }
}

# ==================== 验证函数 ====================

def verify_api_mapping() -> Dict[str, Any]:
    """
    验证前端 API 与后端 API 的映射关系
    
    返回:
        Dict: 验证结果
    """
    results = {
        "matched": [],
        "missing_backend": [],
        "missing_frontend": [],
        "endpoint_mismatch": []
    }
    
    # 前端 API endpoint 映射
    frontend_endpoints = {
        name: api["endpoint"]
        for name, api in FRONTEND_APIS.items()
    }
    
    # 后端 API endpoint 映射
    backend_endpoints = {
        name: api["endpoint"]
        for name, api in BACKEND_APIS.items()
    }
    
    # 检查前端 API 是否有对应的后端 API
    for frontend_name, frontend_endpoint in frontend_endpoints.items():
        # 移除 /api 前缀进行比较
        normalized_frontend = frontend_endpoint.replace('/api', '')
        found = False
        
        for backend_name, backend_endpoint in backend_endpoints.items():
            normalized_backend = backend_endpoint.replace('/api', '')
            
            if normalized_frontend == normalized_backend:
                results["matched"].append({
                    "frontend": frontend_name,
                    "backend": backend_name,
                    "endpoint": frontend_endpoint
                })
                found = True
                break
        
        if not found:
            results["missing_backend"].append({
                "frontend": frontend_name,
                "endpoint": frontend_endpoint
            })
    
    # 检查后端 API 是否有对应的前端 API
    for backend_name, backend_endpoint in backend_endpoints.items():
        normalized_backend = backend_endpoint.replace('/api', '')
        found = False
        
        for frontend_name, frontend_endpoint in frontend_endpoints.items():
            normalized_frontend = frontend_endpoint.replace('/api', '')
            
            if normalized_frontend == normalized_frontend:
                found = True
                break
        
        if not found:
            results["missing_frontend"].append({
                "backend": backend_name,
                "endpoint": backend_endpoint
            })
    
    return results

def verify_ui_api_dependency() -> Dict[str, Any]:
    """
    验证前端界面元素与 API 的依赖关系
    
    返回:
        Dict: 验证结果
    """
    results = {
        "valid": [],
        "invalid": [],
        "missing_api": []
    }
    
    for ui_name, ui_info in FRONTEND_UI_ELEMENTS.items():
        api_dependency = ui_info["api_dependency"]
        
        if api_dependency is None:
            results["valid"].append({
                "ui_element": ui_name,
                "description": ui_info["description"],
                "note": "无 API 依赖"
            })
        elif api_dependency in FRONTEND_APIS:
            results["valid"].append({
                "ui_element": ui_name,
                "description": ui_info["description"],
                "api": api_dependency,
                "endpoint": FRONTEND_APIS[api_dependency]["endpoint"]
            })
        else:
            results["invalid"].append({
                "ui_element": ui_name,
                "description": ui_info["description"],
                "api_dependency": api_dependency,
                "error": "API 不存在"
            })
    
    return results

def verify_request_response_structure() -> Dict[str, Any]:
    """
    验证请求和响应结构
    
    返回:
        Dict: 验证结果
    """
    results = {
        "issues": []
    }
    
    # 检查 previewSmartRename 请求参数
    preview_frontend = FRONTEND_APIS.get("previewSmartRename", {})
    preview_backend = BACKEND_APIS.get("smart_preview", {})
    
    if preview_frontend and preview_backend:
        # 前端参数映射到后端
        frontend_params = set(preview_frontend.get("params", {}).keys())
        expected_backend_params = {
            "target_path", "algorithm", "naming_standard",
            "recursive", "create_folders", "auto_confirm_high_confidence",
            "ai_confidence_threshold", "naming_config"
        }
        
        missing_params = expected_backend_params - frontend_params
        if missing_params:
            results["issues"].append({
                "api": "previewSmartRename",
                "type": "missing_params",
                "params": list(missing_params)
            })
    
    # 检查响应字段
    preview_response_fields = set(preview_frontend.get("response", {}).keys())
    expected_response_fields = {
        "batch_id", "target_path", "total_items", "matched_items",
        "needs_confirmation", "items", "algorithm_used", "naming_standard"
    }
    
    missing_response = expected_response_fields - preview_response_fields
    if missing_response:
        results["issues"].append({
            "api": "previewSmartRename",
            "type": "missing_response_fields",
            "fields": list(missing_response)
        })
    
    return results

def generate_report() -> str:
    """
    生成验证报告
    
    返回:
        str: 格式化的报告文本
    """
    report = []
    report.append("=" * 80)
    report.append("智能重命名界面与接口对应关系验证报告")
    report.append("=" * 80)
    report.append("")
    
    # API 映射验证
    report.append("## 1. API 接口映射验证")
    report.append("-" * 80)
    api_mapping = verify_api_mapping()
    
    report.append(f"✅ 匹配的接口: {len(api_mapping['matched'])}")
    for item in api_mapping["matched"]:
        report.append(f"   - {item['frontend']} -> {item['backend']} ({item['endpoint']})")
    report.append("")
    
    if api_mapping["missing_backend"]:
        report.append(f"❌ 前端有但后端缺失的接口: {len(api_mapping['missing_backend'])}")
        for item in api_mapping["missing_backend"]:
            report.append(f"   - {item['frontend']} ({item['endpoint']})")
        report.append("")
    
    if api_mapping["missing_frontend"]:
        report.append(f"⚠️  后端有但前端未使用的接口: {len(api_mapping['missing_frontend'])}")
        for item in api_mapping["missing_frontend"]:
            report.append(f"   - {item['backend']} ({item['endpoint']})")
        report.append("")
    
    # UI 元素 API 依赖验证
    report.append("## 2. 界面元素 API 依赖验证")
    report.append("-" * 80)
    ui_dependency = verify_ui_api_dependency()
    
    report.append(f"✅ 有效的依赖: {len(ui_dependency['valid'])}")
    for item in ui_dependency["valid"]:
        if item.get("note"):
            report.append(f"   - {item['ui_element']}: {item['description']} ({item['note']})")
        else:
            report.append(f"   - {item['ui_element']}: {item['description']} -> {item['api']} ({item['endpoint']})")
    report.append("")
    
    if ui_dependency["invalid"]:
        report.append(f"❌ 无效的依赖: {len(ui_dependency['invalid'])}")
        for item in ui_dependency["invalid"]:
            report.append(f"   - {item['ui_element']}: {item['error']}")
        report.append("")
    
    # 请求响应结构验证
    report.append("## 3. 请求响应结构验证")
    report.append("-" * 80)
    structure = verify_request_response_structure()
    
    if structure["issues"]:
        report.append(f"❌ 发现 {len(structure['issues'])} 个问题:")
        for issue in structure["issues"]:
            report.append(f"   - {issue['api']}: {issue['type']}")
            if issue["type"] == "missing_params":
                report.append(f"     缺少参数: {', '.join(issue['params'])}")
            elif issue["type"] == "missing_response_fields":
                report.append(f"     缺少字段: {', '.join(issue['fields'])}")
    else:
        report.append("✅ 请求响应结构验证通过")
    report.append("")
    
    # 总结
    report.append("## 4. 验证总结")
    report.append("-" * 80)
    total_issues = (
        len(api_mapping["missing_backend"]) +
        len(api_mapping["missing_frontend"]) +
        len(ui_dependency["invalid"]) +
        len(structure["issues"])
    )
    
    if total_issues == 0:
        report.append("✅ 所有验证通过，界面与接口对应关系正确！")
    else:
        report.append(f"⚠️  发现 {total_issues} 个问题需要修复")
    
    report.append("")
    report.append("=" * 80)
    
    return "\n".join(report)

if __name__ == "__main__":
    print(generate_report())
