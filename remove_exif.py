#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
图片EXIF信息清除工具 v4.0 - Windows版
完全重写，支持格式检测和EXE打包优化
使用ExifTool精确移除EXIF，保持文件大小和朝向
"""

import os
import glob
import sys
import shutil
import subprocess
import tempfile
from pathlib import Path

class ExifRemover:
    def __init__(self):
        self.exiftool_path = None
        self.exiftool_version = None
        self.exe_directory = self.get_exe_directory()
        
    def get_exe_directory(self):
        """获取EXE文件所在目录或脚本目录"""
        if getattr(sys, 'frozen', False):
            # 打包后的EXE环境
            return os.path.dirname(sys.executable)
        else:
            # 开发环境
            return os.path.dirname(os.path.abspath(__file__))
    
    def find_exiftool(self):
        """查找并验证exiftool.exe"""
        possible_paths = [
            os.path.join(self.exe_directory, 'exiftool.exe'),
            os.path.join(self.exe_directory, 'exiftool(-k).exe'),
            'exiftool.exe',  # 系统PATH中
        ]
        
        for path in possible_paths:
            try:
                result = subprocess.run(
                    [path, '-ver'], 
                    capture_output=True, 
                    text=True, 
                    timeout=5, 
                    creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
                )
                if result.returncode == 0:
                    self.exiftool_path = path
                    self.exiftool_version = result.stdout.strip()
                    return True
            except Exception:
                continue
        
        return False
    
    def get_file_info(self, file_path):
        """获取文件的详细信息"""
        try:
            # 获取文件类型
            result = subprocess.run(
                [self.exiftool_path, '-s', '-s', '-s', '-FileType', file_path], 
                capture_output=True, 
                text=True, 
                timeout=10,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
            )
            
            if result.returncode != 0:
                return None, False, "无法读取文件信息"
            
            file_type = result.stdout.strip().upper()
            
            # 检查是否为支持的图片格式
            supported_types = ['JPEG', 'PNG', 'TIFF', 'WEBP', 'BMP']
            if file_type not in supported_types:
                return file_type, False, f"不支持的格式: {file_type}"
            
            # 检查是否有EXIF数据
            result = subprocess.run(
                [self.exiftool_path, '-s', '-s', '-s', '-EXIF:all', file_path], 
                capture_output=True, 
                text=True, 
                timeout=10,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
            )
            
            has_exif = len(result.stdout.strip()) > 0
            
            return file_type, has_exif, None
            
        except Exception as e:
            return None, False, str(e)
    
    def check_format_mismatch(self, file_path, actual_format):
        """检查文件扩展名是否与实际格式匹配"""
        _, ext = os.path.splitext(file_path)
        ext = ext.lower()
        
        if actual_format == 'JPEG' and ext not in ['.jpg', '.jpeg']:
            return True
        elif actual_format == 'PNG' and ext != '.png':
            return True
        elif actual_format == 'TIFF' and ext not in ['.tiff', '.tif']:
            return True
        elif actual_format == 'WEBP' and ext != '.webp':
            return True
        elif actual_format == 'BMP' and ext != '.bmp':
            return True
        
        return False
    
    def get_correct_extension(self, actual_format):
        """根据实际格式获取正确的扩展名"""
        format_map = {
            'JPEG': '.jpg',
            'PNG': '.png',
            'TIFF': '.tiff',
            'WEBP': '.webp',
            'BMP': '.bmp'
        }
        return format_map.get(actual_format, '.tmp')
    
    def remove_exif_data(self, file_path, actual_format, create_backup=False):
        """移除EXIF数据"""
        try:
            original_size = os.path.getsize(file_path)
            
            # 创建备份
            if create_backup:
                name, ext = os.path.splitext(file_path)
                backup_path = f"{name}_backup{ext}"
                counter = 1
                while os.path.exists(backup_path):
                    backup_path = f"{name}_backup_{counter}{ext}"
                    counter += 1
                
                shutil.copy2(file_path, backup_path)
                print(f"    备份: {backup_path}")
            
            # 检查格式不匹配
            format_mismatch = self.check_format_mismatch(file_path, actual_format)
            temp_file = None
            working_file = file_path
            
            if format_mismatch:
                # 创建临时文件，使用正确的扩展名
                correct_ext = self.get_correct_extension(actual_format)
                temp_dir = tempfile.gettempdir()
                temp_name = f"exif_temp_{os.getpid()}_{hash(file_path) % 10000}{correct_ext}"
                temp_file = os.path.join(temp_dir, temp_name)
                
                shutil.copy2(file_path, temp_file)
                working_file = temp_file
                print(f"    使用临时文件处理格式不匹配问题")
            
            # ExifTool命令
            cmd = [
                self.exiftool_path,
                '-overwrite_original',
                '-all=',
                '-TagsFromFile', '@',
                '-orientation',
                working_file
            ]
            
            result = subprocess.run(
                cmd, 
                capture_output=True, 
                text=True, 
                timeout=30,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
            )
            
            success = False
            if result.returncode == 0:
                # 如果使用了临时文件，复制回原文件
                if temp_file and os.path.exists(temp_file):
                    shutil.copy2(temp_file, file_path)
                    try:
                        os.remove(temp_file)
                    except:
                        pass  # 临时文件删除失败不影响主要功能
                
                new_size = os.path.getsize(file_path)
                size_change = new_size - original_size
                print(f"    ✓ 成功 (大小变化: {size_change:+d} 字节)")
                success = True
            else:
                error_msg = result.stderr.strip()
                if error_msg:
                    print(f"    ✗ 失败: {error_msg}")
                else:
                    print(f"    ✗ 失败: ExifTool返回错误")
            
            # 清理临时文件
            if temp_file and os.path.exists(temp_file):
                try:
                    os.remove(temp_file)
                except:
                    pass
            
            return success
            
        except subprocess.TimeoutExpired:
            print(f"    ✗ 处理超时")
            return False
        except Exception as e:
            print(f"    ✗ 错误: {str(e)}")
            return False
    
    def get_image_files(self):
        """获取当前目录下的图片文件"""
        os.chdir(self.exe_directory)
        
        extensions = ['*.jpg', '*.jpeg', '*.png', '*.tiff', '*.tif', '*.webp', '*.bmp']
        image_files = []
        
        for ext in extensions:
            image_files.extend(glob.glob(ext))
            image_files.extend(glob.glob(ext.upper()))
        
        return sorted(list(set(image_files)))
    
    def show_installation_guide(self):
        """显示ExifTool安装指南"""
        print("=" * 60)
        print("       需要 ExifTool")
        print("=" * 60)
        print()
        print("ExifTool 是专业的元数据处理工具。")
        print()
        print("📥 下载安装:")
        print("1. 访问: https://exiftool.org/")
        print("2. 点击 'Windows Executable' 下载")
        print("3. 解压得到 exiftool(-k).exe")
        print("4. 将文件重命名为 exiftool.exe")
        print("5. 放到本程序同一目录下")
        print()
        print("💡 提示:")
        print("- 文件大小约 6MB")
        print("- 绿色免安装，无需系统管理员权限")
        print("- 放好后重新运行本程序")
        print()
        print(f"当前程序目录: {self.exe_directory}")
        print()
    
    def run(self):
        """主运行函数"""
        print("图片EXIF清除工具 v4.0 - Windows版")
        print("=" * 60)
        
        # 检查ExifTool
        if not self.find_exiftool():
            self.show_installation_guide()
            input("按回车键退出...")
            return
        
        print(f"✓ ExifTool {self.exiftool_version}")
        print()
        
        # 获取图片文件
        try:
            image_files = self.get_image_files()
        except Exception as e:
            print(f"错误: 无法读取目录 - {str(e)}")
            input("按回车键退出...")
            return
        
        if not image_files:
            print("当前目录下没有找到图片文件")
            print("支持格式: JPG, JPEG, PNG, TIFF, TIF, WEBP, BMP")
            print(f"当前目录: {self.exe_directory}")
            input("按回车键退出...")
            return
        
        print(f"找到 {len(image_files)} 个可能的图片文件")
        print()
        
        # 分析文件
        valid_files = []
        files_with_exif = []
        format_issues = []
        file_info = {}
        
        print("检查文件格式和EXIF数据...")
        
        for i, file in enumerate(image_files, 1):
            print(f"  [{i:2d}/{len(image_files)}] {file}", end="")
            
            file_type, has_exif, error = self.get_file_info(file)
            
            if error:
                print(f" [错误: {error}]")
                continue
            
            valid_files.append(file)
            file_info[file] = {
                'type': file_type,
                'has_exif': has_exif,
                'format_mismatch': self.check_format_mismatch(file, file_type)
            }
            
            status = [f"类型: {file_type}"]
            
            if file_info[file]['format_mismatch']:
                status.append("⚠️ 扩展名不匹配")
                format_issues.append((file, file_type))
            
            if has_exif:
                status.append("有EXIF")
                files_with_exif.append(file)
            else:
                status.append("无EXIF")
            
            print(f" [{', '.join(status)}]")
        
        print()
        
        if not valid_files:
            print("没有发现有效的图片文件")
            input("按回车键退出...")
            return
        
        # 显示格式问题警告
        if format_issues:
            print(f"⚠️  发现 {len(format_issues)} 个文件扩展名与实际格式不匹配:")
            for file, actual_type in format_issues:
                print(f"  - {file} (实际格式: {actual_type})")
            print("  这些文件仍可正常处理，程序会自动处理格式不匹配问题")
            print()
        
        if not files_with_exif:
            print(f"没有发现包含EXIF数据的图片 (共检查了 {len(valid_files)} 个有效文件)")
            input("按回车键退出...")
            return
        
        print(f"需要处理 {len(files_with_exif)} 个包含EXIF数据的文件:")
        for file in files_with_exif:
            print(f"  - {file}")
        
        print()
        print("处理优势:")
        print("• 精确移除EXIF，不重新编码图片")
        print("• 保持图片正确朝向")
        print("• 文件大小几乎不变")
        print("• 完全保持画质")
        print("• 自动处理格式不匹配问题")
        print()
        print("注意: 将删除拍摄信息、GPS位置、相机参数等元数据")
        print()
        
        # 确认处理
        while True:
            choice = input("继续处理这些文件? (Y/N): ").strip().upper()
            if choice in ['Y', 'YES', '是']:
                break
            elif choice in ['N', 'NO', '否']:
                print("已取消操作")
                input("按回车键退出...")
                return
            else:
                print("请输入 Y 或 N")
        
        # 询问备份
        while True:
            backup_choice = input("是否创建备份文件? (Y/N): ").strip().upper()
            if backup_choice in ['Y', 'YES', '是']:
                create_backup = True
                break
            elif backup_choice in ['N', 'NO', '否']:
                create_backup = False
                break
            else:
                print("请输入 Y 或 N")
        
        print()
        print("开始处理...")
        print("=" * 60)
        
        # 处理文件
        processed = 0
        failed = 0
        total_size_change = 0
        
        for i, file in enumerate(files_with_exif, 1):
            print(f"[{i:2d}/{len(files_with_exif)}] {file}")
            original_size = os.path.getsize(file)
            actual_format = file_info[file]['type']
            
            if self.remove_exif_data(file, actual_format, create_backup):
                processed += 1
                new_size = os.path.getsize(file)
                total_size_change += (new_size - original_size)
            else:
                failed += 1
        
        # 显示结果
        print()
        print("=" * 60)
        print("处理完成!")
        print(f"✓ 成功处理: {processed} 个文件")
        if failed > 0:
            print(f"✗ 处理失败: {failed} 个文件")
        
        if processed > 0:
            if total_size_change < 0:
                print(f"📉 总大小减少: {abs(total_size_change)} 字节")
            elif total_size_change > 0:
                print(f"📈 总大小增加: {total_size_change} 字节")
            else:
                print("📊 文件大小无变化")
        
        print("=" * 60)
        input("按回车键退出...")

def main():
    """主函数"""
    try:
        remover = ExifRemover()
        remover.run()
    except KeyboardInterrupt:
        print("\n\n⚠️  用户中断操作")
        input("按回车键退出...")
    except Exception as e:
        print(f"\n❌ 程序发生异常: {str(e)}")
        print("请检查文件是否被其他程序占用，或联系开发者")
        input("按回车键退出...")

if __name__ == "__main__":
    main()