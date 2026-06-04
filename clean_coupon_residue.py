import os
import re
import shutil

# 配置项目根目录（默认当前目录）
PROJECT_DIR = os.path.abspath(os.path.dirname(__file__))

# 需要扫描的文件类型
TARGET_EXTENSIONS = ['.py', '.html', '.js', '.json', '.md']

# 排除不需要扫描的目录
EXCLUDE_DIRS = ['venv', '.git', '__pycache__', 'instance', 'backups', 'static/uploads']

def scan_and_clean_coupons(dry_run=True):
    """
    扫描并清理优惠券残留代码
    :param dry_run: 如果为 True，仅打印发现的残留，不修改文件；如果为 False，则直接修改文件。
    """
    print(f"[{'预览模式' if dry_run else '实操执行'}] 开始扫描目录: {PROJECT_DIR}\n" + "="*60)
    
    coupon_pattern = re.compile(r'\bcoupon\b', re.IGNORECASE)
    total_matches = 0
    modified_files_count = 0

    for root, dirs, files in os.walk(PROJECT_DIR):
        # 过滤排除目录
        dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]
        
        for file in files:
            if not any(file.endswith(ext) for ext in TARGET_EXTENSIONS):
                continue
                
            file_path = os.path.join(root, file)
            
            # 跳过脚本自身
            if file == os.path.basename(__file__):
                continue

            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    lines = f.readlines()
            except Exception as e:
                print(f"无法读取文件 {file_path}: {e}")
                continue

            file_has_coupon = False
            new_lines = []
            file_matches = 0

            for line_idx, line in enumerate(lines, 1):
                if coupon_pattern.search(line):
                    file_has_coupon = True
                    file_matches += 1
                    total_matches += 1
                    print(f"发现残留 -> 物理路径: {os.path.relpath(file_path, PROJECT_DIR)} | 行号: {line_idx}")
                    print(f"        内容: {line.strip()}")
                    
                    # 智能过滤逻辑：如果是单行包含 coupon，则在执行模式下直接忽略该行（整行删除或注释）
                    # 注意：如果存在复杂的跨行代码块，建议根据此处的打印手动微调
                    continue 
                
                new_lines.append(line)

            if file_has_coupon:
                print(f"--> 该文件共发现 {file_matches} 处优惠券相关代码。\n" + "-"*50)
                
                if not dry_run:
                    # 创建备份
                    shutil.copy2(file_path, file_path + '.bak')
                    try:
                        with open(file_path, 'w', encoding='utf-8') as f:
                            f.writelines(new_lines)
                        modified_files_count += 1
                    except Exception as e:
                        print(f"写入文件失败 {file_path}: {e}")

    print("="*60)
    print(f"扫描结束！总共发现 {total_matches} 处 'coupon' 残留。")
    if dry_run:
        print("提示：当前为预览模式，未对文件做出任何修改。确认无误后，请将代码中的 `dry_run=True` 改为 `False` 执行清理。")
    else:
        print(f"清理完成！已成功自动修改并备份了 {modified_files_count} 个文件（生成了 .bak 备份文件）。")

if __name__ == "__main__":
    # 第一次运行强烈建议保持 True 进行预览，确认安全后再改为 False
    scan_and_clean_coupons(False)