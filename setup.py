"""Setup configuration for Sol with post-install hooks."""

from pathlib import Path
import shutil
import atexit
from setuptools import setup
from setuptools.command.develop import develop
from setuptools.command.install import install


def install_skills_to_agents():
    """Copy skills to ~/.agents/skills/ after installation."""
    
    try:
        # Find skills directory relative to this setup.py
        setup_dir = Path(__file__).parent
        skills_source = setup_dir / "src" / "skills"
        
        if not skills_source.exists():
            # Try to find from installed package
            try:
                import sol
                package_dir = Path(sol.__file__).parent.parent
                skills_source = package_dir / "skills"
            except ImportError:
                pass
        
        if not skills_source.exists():
            print(f"⚠️  Skills directory not found")
            return
        
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
            
            # Remove existing
            if target.exists():
                shutil.rmtree(target)
            
            # Copy
            shutil.copytree(skill_dir, target)
            installed.append(skill_dir.name)
        
        # Report
        if installed:
            print("\n" + "=" * 60)
            print(f"✨ Installed {len(installed)} Sol skill(s) to ~/.agents/skills/:")
            for name in installed:
                print(f"   • {name}")
            print("=" * 60 + "\n")
    
    except Exception as e:
        print(f"⚠️  Warning: Failed to install skills: {e}")
        # Don't fail the installation if skills copy fails


# Register atexit handler to run after installation
atexit.register(install_skills_to_agents)


class PostInstallCommand(install):
    """Post-installation hook."""
    
    def run(self):
        install.run(self)
        install_skills_to_agents()


class PostDevelopCommand(develop):
    """Post-develop (editable) install hook."""
    
    def run(self):
        develop.run(self)
        install_skills_to_agents()


if __name__ == "__main__":
    setup(
        cmdclass={
            'install': PostInstallCommand,
            'develop': PostDevelopCommand,
        },
    )
