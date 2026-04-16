#!/usr/bin/env python3
"""Install Sol skills to ~/.agents/skills/"""

import shutil
import sys
from pathlib import Path


def install_skills():
    """Copy skills from package to ~/.agents/skills/"""
    
    try:
        # 1. Find installed package location
        import sol
        package_dir = Path(sol.__file__).parent.parent
        skills_source = package_dir / "skills"
        
        if not skills_source.exists():
            print(f"⚠️  Skills directory not found at {skills_source}", file=sys.stderr)
            print(f"    Package location: {package_dir}", file=sys.stderr)
            return 1
        
        # 2. Target directory
        agents_dir = Path.home() / ".agents" / "skills"
        agents_dir.mkdir(parents=True, exist_ok=True)
        
        # 3. Copy each skill
        installed = []
        for skill_dir in skills_source.iterdir():
            # Skip non-directories and Python cache
            if not skill_dir.is_dir() or skill_dir.name.startswith(("__", ".")):
                continue
            
            # Skip README and __init__.py
            if skill_dir.name in ("README.md", "__init__.py"):
                continue
            
            target = agents_dir / skill_dir.name
            
            # Remove existing if present
            if target.exists():
                shutil.rmtree(target)
                print(f"🔄 Updating: {skill_dir.name}")
            else:
                print(f"📦 Installing: {skill_dir.name}")
            
            # Copy skill directory
            shutil.copytree(skill_dir, target)
            installed.append(skill_dir.name)
            print(f"   ✅ {target}")
        
        # 4. Summary
        if installed:
            print(f"\n✨ Successfully installed {len(installed)} skill(s):")
            for name in installed:
                print(f"   • {name}")
            print(f"\n📁 Location: {agents_dir}")
            return 0
        else:
            print("⚠️  No skills found to install", file=sys.stderr)
            return 1
    
    except ImportError:
        print("❌ Sol package not found. Please install sol first:", file=sys.stderr)
        print("   pip install sol", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"❌ Error installing skills: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(install_skills())
