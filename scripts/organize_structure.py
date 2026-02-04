#!/usr/bin/env python3
"""
项目结构整理脚本

用途: 自动化执行项目文件结构整理，包括目录创建、文件移动和重命名
输入: 无（使用预定义的整理规则）
输出: 整理操作日志和结果报告
副作用:
    - 创建新的目录结构
    - 移动和重命名文件
    - 生成操作日志文件
"""

import os
import shutil
from pathlib import Path
from datetime import datetime
from typing import List, Tuple, Dict
import json

class StructureOrganizer:
    """
    项目结构整理器
    
    用途: 管理项目文件结构的整理操作
    """
    
    def __init__(self, project_root: str):
        """
        初始化整理器
        
        输入:
            - project_root (str): 项目根目录路径
        输出: 无
        副作用: 初始化日志文件
        """
        self.root = Path(project_root)
        self.log_file = self.root / "logs" / f"structure_organize_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
        self.operations: List[Dict] = []
        
    def log(self, message: str, level: str = "INFO"):
        """
        记录日志
        
        输入:
            - message (str): 日志消息
            - level (str): 日志级别，默认 "INFO"
        输出: 无
        副作用: 写入日志到文件和控制台
        """
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_message = f"[{timestamp}] [{level}] {message}"
        print(log_message)
        
        # 确保日志目录存在
        self.log_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.log_file, "a", encoding="utf-8") as f:
            f.write(log_message + "\n")
    
    def create_directory(self, dir_path: Path):
        """
        创建目录
        
        输入:
            - dir_path (Path): 目录路径
        输出: bool - 是否成功创建
        副作用: 创建目录到文件系统
        """
        try:
            if not dir_path.exists():
                dir_path.mkdir(parents=True, exist_ok=True)
                self.log(f"✅ 创建目录: {dir_path.relative_to(self.root)}")
                self.operations.append({
                    "type": "create_dir",
                    "path": str(dir_path.relative_to(self.root)),
                    "status": "success"
                })
                return True
            else:
                self.log(f"⏭️  目录已存在: {dir_path.relative_to(self.root)}", "DEBUG")
                return True
        except Exception as e:
            self.log(f"❌ 创建目录失败: {dir_path.relative_to(self.root)} - {e}", "ERROR")
            self.operations.append({
                "type": "create_dir",
                "path": str(dir_path.relative_to(self.root)),
                "status": "failed",
                "error": str(e)
            })
            return False
    
    def move_file(self, src: Path, dst: Path, create_parent: bool = True):
        """
        移动文件
        
        输入:
            - src (Path): 源文件路径
            - dst (Path): 目标文件路径
            - create_parent (bool): 是否创建父目录，默认 True
        输出: bool - 是否成功移动
        副作用: 移动文件到新位置
        """
        try:
            if not src.exists():
                self.log(f"⚠️  源文件不存在: {src.relative_to(self.root)}", "WARNING")
                return False
            
            if dst.exists():
                self.log(f"⚠️  目标文件已存在: {dst.relative_to(self.root)}", "WARNING")
                return False
            
            if create_parent:
                dst.parent.mkdir(parents=True, exist_ok=True)
            
            shutil.move(str(src), str(dst))
            self.log(f"✅ 移动文件: {src.relative_to(self.root)} → {dst.relative_to(self.root)}")
            self.operations.append({
                "type": "move_file",
                "src": str(src.relative_to(self.root)),
                "dst": str(dst.relative_to(self.root)),
                "status": "success"
            })
            return True
        except Exception as e:
            self.log(f"❌ 移动文件失败: {src.relative_to(self.root)} → {dst.relative_to(self.root)} - {e}", "ERROR")
            self.operations.append({
                "type": "move_file",
                "src": str(src.relative_to(self.root)),
                "dst": str(dst.relative_to(self.root)),
                "status": "failed",
                "error": str(e)
            })
            return False
    
    def create_readme(self, dir_path: Path, content: str):
        """
        创建 README 文件
        
        输入:
            - dir_path (Path): 目录路径
            - content (str): README 内容
        输出: bool - 是否成功创建
        副作用: 写入 README.md 文件
        """
        try:
            readme_path = dir_path / "README.md"
            if readme_path.exists():
                self.log(f"⏭️  README 已存在: {readme_path.relative_to(self.root)}", "DEBUG")
                return True
            
            with open(readme_path, "w", encoding="utf-8") as f:
                f.write(content)
            
            self.log(f"✅ 创建 README: {readme_path.relative_to(self.root)}")
            self.operations.append({
                "type": "create_readme",
                "path": str(readme_path.relative_to(self.root)),
                "status": "success"
            })
            return True
        except Exception as e:
            self.log(f"❌ 创建 README 失败: {dir_path.relative_to(self.root)} - {e}", "ERROR")
            self.operations.append({
                "type": "create_readme",
                "path": str(dir_path.relative_to(self.root)),
                "status": "failed",
                "error": str(e)
            })
            return False
    
    def organize_root_docs(self):
        """
        整理根目录文档
        
        用途: 将根目录的中文文档移动到 docs/ 目录
        输入: 无
        输出: 无
        副作用: 移动文档文件
        """
        self.log("=" * 60)
        self.log("阶段 1: 整理根目录文档")
        self.log("=" * 60)
        
        # 创建 docs 目录（如果不存在）
        docs_dir = self.root / "docs"
        self.create_directory(docs_dir)
        
        # 移动根目录的中文文档
        doc_files = [
            ("历史指令.md", "docs/history.md"),
            ("开发方案.md", "docs/development_plan.md"),
            ("测试报告.md", "docs/test_report.md"),
        ]
        
        for src_name, dst_name in doc_files:
            src = self.root / src_name
            dst = self.root / dst_name
            if src.exists():
                self.move_file(src, dst)
    
    def organize_scripts(self):
        """
        整理脚本目录
        
        用途: 按功能分类整理脚本文件
        输入: 无
        输出: 无
        副作用: 创建子目录并移动脚本
        """
        self.log("=" * 60)
        self.log("阶段 2: 整理脚本目录")
        self.log("=" * 60)
        
        scripts_dir = self.root / "scripts"
        
        # 创建脚本分类目录
        subdirs = {
            "verification": "验证脚本",
            "utils": "工具脚本"
        }
        
        for subdir, desc in subdirs.items():
            dir_path = scripts_dir / subdir
            self.create_directory(dir_path)
            self.create_readme(dir_path, f"# {desc}\n\n本目录包含{desc}。\n")
        
        # 移动验证脚本
        verification_scripts = [
            "comprehensive_verification_report.py",
            "verify_smart_rename_mapping.py",
            "verify_ui_completeness.py"
        ]
        
        for script in verification_scripts:
            src = scripts_dir / script
            dst = scripts_dir / "verification" / script
            if src.exists() and not dst.exists():
                self.move_file(src, dst)
    
    def create_docs_structure(self):
        """
        创建文档目录结构
        
        用途: 建立规范的文档目录结构
        输入: 无
        输出: 无
        副作用: 创建文档目录和 README 文件
        """
        self.log("=" * 60)
        self.log("阶段 3: 创建文档目录结构")
        self.log("=" * 60)
        
        docs_dir = self.root / "docs"
        
        # 文档目录结构
        doc_structure = {
            "guides": "使用指南",
            "architecture": "架构文档",
            "development": "开发文档",
            "operations": "运维文档",
            "api": "API 文档"
        }
        
        for subdir, desc in doc_structure.items():
            dir_path = docs_dir / subdir
            self.create_directory(dir_path)
            self.create_readme(dir_path, f"# {desc}\n\n本目录包含{desc}。\n")
        
        # 创建文档索引
        index_content = """# 项目文档索引

本目录包含 quark_strm 项目的所有文档。

## 📁 目录结构

- **guides/** - 使用指南
  - 快速开始、配置说明、功能使用等

- **architecture/** - 架构文档
  - 系统架构、技术选型、设计方案等

- **development/** - 开发文档
  - 开发计划、实施记录、历史指令等

- **operations/** - 运维文档
  - 部署指南、监控配置、故障排查等

- **api/** - API 文档
  - API 接口说明、使用示例等

## 📝 主要文档

- `development_plan.md` - 开发方案
- `test_report.md` - 测试报告
- `history.md` - 历史指令记录
"""
        self.create_readme(docs_dir, index_content)
    
    def generate_report(self):
        """
        生成整理报告
        
        用途: 生成操作摘要报告
        输入: 无
        输出: 无
        副作用: 写入报告文件
        """
        self.log("=" * 60)
        self.log("生成整理报告")
        self.log("=" * 60)
        
        # 统计操作结果
        total = len(self.operations)
        success = sum(1 for op in self.operations if op["status"] == "success")
        failed = sum(1 for op in self.operations if op["status"] == "failed")
        
        report = f"""# 项目结构整理报告

## 执行时间
{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

## 操作统计
- 总操作数: {total}
- 成功: {success}
- 失败: {failed}
- 成功率: {(success/total*100 if total > 0 else 0):.1f}%

## 操作详情

"""
        
        # 按类型分组
        ops_by_type = {}
        for op in self.operations:
            op_type = op["type"]
            if op_type not in ops_by_type:
                ops_by_type[op_type] = []
            ops_by_type[op_type].append(op)
        
        for op_type, ops in ops_by_type.items():
            report += f"\n### {op_type}\n\n"
            for op in ops:
                status_icon = "✅" if op["status"] == "success" else "❌"
                if op_type == "move_file":
                    report += f"- {status_icon} {op['src']} → {op['dst']}\n"
                else:
                    report += f"- {status_icon} {op['path']}\n"
                if op["status"] == "failed":
                    report += f"  - 错误: {op.get('error', 'Unknown')}\n"
        
        # 保存报告
        report_path = self.root / "docs" / "structure_organization_report.md"
        with open(report_path, "w", encoding="utf-8") as f:
            f.write(report)
        
        self.log(f"✅ 报告已生成: {report_path.relative_to(self.root)}")
        
        # 保存 JSON 格式的操作记录
        json_path = self.log_file.with_suffix(".json")
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(self.operations, f, indent=2, ensure_ascii=False)
        
        self.log(f"✅ JSON 记录已保存: {json_path.relative_to(self.root)}")
        
        # 打印摘要
        self.log("=" * 60)
        self.log(f"整理完成！总操作数: {total}, 成功: {success}, 失败: {failed}")
        self.log(f"详细日志: {self.log_file.relative_to(self.root)}")
        self.log(f"整理报告: {report_path.relative_to(self.root)}")
        self.log("=" * 60)


def main():
    """
    主函数
    
    用途: 执行项目结构整理
    输入: 无
    输出: 无
    副作用: 整理项目文件结构
    """
    # 获取项目根目录
    script_dir = Path(__file__).parent
    project_root = script_dir.parent
    
    print(f"项目根目录: {project_root}")
    print("开始整理项目结构...")
    print()
    
    # 创建整理器
    organizer = StructureOrganizer(str(project_root))
    
    try:
        # 执行整理操作
        organizer.organize_root_docs()
        organizer.organize_scripts()
        organizer.create_docs_structure()
        
        # 生成报告
        organizer.generate_report()
        
        print("\n✅ 项目结构整理完成！")
        return 0
        
    except Exception as e:
        organizer.log(f"❌ 整理过程发生错误: {e}", "CRITICAL")
        print(f"\n❌ 整理失败: {e}")
        return 1


if __name__ == "__main__":
    exit(main())
