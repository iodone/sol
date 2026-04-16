"""Install Sol skills to ~/.agents/skills/

This module provides a standalone installation function for Sol skills.
It's automatically called during package installation (via atexit hook),
but can also be invoked manually if needed.
"""

from pathlib import Path
import shutil
import sys


def install_skills() -> int:
    """Install skills from package to ~/.agents/skills/
    
    Returns:
        0 on success, 1 on failure
    """
    
    try:
        # Find skills directory from installed package
        import sol
        package_dir = Path(sol.__file__).parent.parent
        skills_source = package_dir / "skills"
        
        if not skills_source.exists():
            print(f"⚠️  Skills directory not found at {skills_source}", file=sys.stderr)
            print(f"    Package location: {package_dir}", file=sys.stderr)
            return 1
        
        # Target directory
        agents_dir = Path.home() / ".agents" / "skills"
        agents_dir.mkdir(parents=True, exist_ok=True)
        
        # Copy each skill
        installed = []
        for skill_dir in skills_source.iterdir():
            # Skip non-directories, Python cache, README, __init__
            if not skill_dir.is_dir():
                continue
            if skill_dir.name.startswith(("__", ".")):
                continue
            if skill_dir.name in ("README.md",):
                continue
            
            target = agents_dir / skill_dir.name
            
            # Remove existing (覆盖逻辑)
            if target.exists():
                shutil.rmtree(target)
                print(f"🔄 Updating: {skill_dir.name}")
            else:
                print(f"📦 Installing: {skill_dir.name}")
            
            # Copy
            shutil.copytree(skill_dir, target)
            installed.append(skill_dir.name)
            print(f"   ✅ {target}")
        
        # Summary
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
        print("   uv sync", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"❌ Error installing skills: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return 1


def main():
    """CLI entry point"""
    sys.exit(install_skills())


if __name__ == "__main__":
    main()
