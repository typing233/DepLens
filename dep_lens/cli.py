import json
from pathlib import Path
from typing import Optional

import click
from colorama import Fore, Style, init

from .analyzer import AnalysisResult, analyze_project
from .detector import ProjectType
from .dot_generator import generate_dot
from .output import print_results

init(autoreset=True)


@click.group()
@click.version_option(version="0.1.0", prog_name="deplens")
def cli():
    """DepLens - A powerful dependency analyzer for Node.js, Python, and Rust projects."""
    pass


@cli.command()
@click.argument("project_path", type=click.Path(exists=True, file_okay=False, path_type=Path))
@click.option(
    "--dot", "-d", 
    type=click.Path(path_type=Path), 
    help="Generate DOT file for Graphviz visualization"
)
@click.option(
    "--json", "-j", 
    type=click.Path(path_type=Path), 
    help="Export analysis results to JSON file"
)
@click.option(
    "--no-color", 
    is_flag=True, 
    help="Disable colored output"
)
@click.option(
    "--no-tree", 
    is_flag=True, 
    help="Do not display dependency tree"
)
@click.option(
    "--no-issues", 
    is_flag=True, 
    help="Do not display issues summary"
)
@click.option(
    "--no-stats", 
    is_flag=True, 
    help="Do not display statistics"
)
def analyze(
    project_path: Path,
    dot: Optional[Path] = None,
    json: Optional[Path] = None,
    no_color: bool = False,
    no_tree: bool = False,
    no_issues: bool = False,
    no_stats: bool = False,
):
    """Analyze dependencies of a project.
    
    PROJECT_PATH is the path to the project directory to analyze.
    """
    project_path = project_path.resolve()
    
    click.echo(f"\n{Fore.CYAN}🔍 Analyzing project: {Style.BRIGHT}{project_path}{Style.RESET_ALL}\n")
    
    result = analyze_project(project_path)
    
    if result.project_type == ProjectType.UNKNOWN:
        click.echo(f"{Fore.RED}❌ Error: Could not detect project type.{Style.RESET_ALL}")
        click.echo(f"{Fore.YELLOW}💡 Make sure the project has one of: package.json, requirements.txt, pyproject.toml, Cargo.toml{Style.RESET_ALL}")
        raise click.ClickException("Unknown project type")
    
    click.echo(f"{Fore.GREEN}✅ Detected project type: {Style.BRIGHT}{result.project_type.value.upper()}{Style.RESET_ALL}")
    click.echo(f"{Fore.GREEN}✅ Found indicators: {', '.join(result.indicators)}{Style.RESET_ALL}\n")
    
    if not no_color:
        if not no_tree:
            print_results(result)
        else:
            if not no_issues:
                from .output import TreePrinter
                printer = TreePrinter(result)
                printer.print_issues()
            if not no_stats:
                from .output import TreePrinter
                printer = TreePrinter(result)
                printer.print_statistics()
    else:
        _print_plain_text(result, no_tree, no_issues, no_stats)
    
    if dot:
        dot_path = dot.resolve()
        generate_dot(result, dot_path)
        click.echo(f"{Fore.GREEN}📄 DOT file generated: {Style.BRIGHT}{dot_path}{Style.RESET_ALL}")
        
        dot_svg_path = dot_path.with_suffix(".svg")
        click.echo(f"{Fore.BLUE}💡 Tip: Use 'dot -Tsvg {dot_path} -o {dot_svg_path}' to generate SVG visualization{Style.RESET_ALL}")
    
    if json:
        json_path = json.resolve()
        _export_to_json(result, json_path)
        click.echo(f"{Fore.GREEN}📋 JSON report generated: {Style.BRIGHT}{json_path}{Style.RESET_ALL}")
    
    issue_count = (
        len(result.circular_dependencies)
        + len(result.ghost_dependencies)
        + len(result.version_conflicts)
    )
    
    if issue_count > 0:
        click.echo(f"\n{Fore.YELLOW}⚠️  Found {issue_count} issue(s) that need attention.{Style.RESET_ALL}")
        raise click.ClickException("Dependency issues detected")
    else:
        click.echo(f"\n{Fore.GREEN}✅ All checks passed! No dependency issues found.{Style.RESET_ALL}")


@cli.command()
@click.argument("project_path", type=click.Path(exists=True, file_okay=False, path_type=Path))
@click.option(
    "--output", "-o", 
    type=click.Path(path_type=Path), 
    default="dependencies.dot",
    help="Output DOT file path (default: dependencies.dot)"
)
def dot(project_path: Path, output: Path):
    """Generate DOT file for Graphviz visualization.
    
    PROJECT_PATH is the path to the project directory to analyze.
    """
    project_path = project_path.resolve()
    output_path = output.resolve()
    
    click.echo(f"\n{Fore.CYAN}🔍 Analyzing project: {Style.BRIGHT}{project_path}{Style.RESET_ALL}\n")
    
    result = analyze_project(project_path)
    
    if result.project_type == ProjectType.UNKNOWN:
        click.echo(f"{Fore.RED}❌ Error: Could not detect project type.{Style.RESET_ALL}")
        raise click.ClickException("Unknown project type")
    
    generate_dot(result, output_path)
    
    click.echo(f"{Fore.GREEN}✅ DOT file generated: {Style.BRIGHT}{output_path}{Style.RESET_ALL}")
    click.echo(f"\n{Fore.BLUE}💡 Next steps:{Style.RESET_ALL}")
    click.echo(f"   {Fore.CYAN}•{Style.RESET_ALL} Generate PNG:  {Style.BRIGHT}dot -Tpng {output_path} -o dependencies.png{Style.RESET_ALL}")
    click.echo(f"   {Fore.CYAN}•{Style.RESET_ALL} Generate SVG:  {Style.BRIGHT}dot -Tsvg {output_path} -o dependencies.svg{Style.RESET_ALL}")
    click.echo(f"   {Fore.CYAN}•{Style.RESET_ALL} Generate PDF:  {Style.BRIGHT}dot -Tpdf {output_path} -o dependencies.pdf{Style.RESET_ALL}")


def _print_plain_text(
    result: AnalysisResult, 
    no_tree: bool = False, 
    no_issues: bool = False,
    no_stats: bool = False
) -> None:
    print(f"Project: {result.project_path.name}")
    print(f"Type: {result.project_type.value}")
    print(f"Direct dependencies: {len(result.direct_dependencies)}")
    print(f"Total dependencies: {len(result.all_dependencies)}")
    print(f"Dev dependencies: {len(result.dev_dependencies)}")
    print()
    
    if not no_tree:
        print("Dependency Tree:")
        for name, dep in result.direct_dependencies.items():
            print(f"  - {name} (v{dep.version})")
            for child in dep.dependencies:
                print(f"    - {child.name} (v{child.version})")
        print()
    
    if not no_issues:
        print("Issues:")
        if result.circular_dependencies:
            print("  Circular Dependencies:")
            for cd in result.circular_dependencies:
                print(f"    - {' -> '.join(cd.path)}")
        if result.ghost_dependencies:
            print("  Ghost Dependencies:")
            for gd in result.ghost_dependencies:
                print(f"    - {gd.name}")
        if result.version_conflicts:
            print("  Version Conflicts:")
            for vc in result.version_conflicts:
                print(f"    - {vc.name}: {', '.join(vc.versions.keys())}")
        if not (result.circular_dependencies or result.ghost_dependencies or result.version_conflicts):
            print("  No issues found.")
        print()
    
    if not no_stats:
        print("Statistics:")
        print(f"  Direct: {len(result.direct_dependencies)}")
        print(f"  Total: {len(result.all_dependencies)}")
        print(f"  Dev: {len(result.dev_dependencies)}")


def _export_to_json(result: AnalysisResult, output_path: Path) -> None:
    def dep_to_dict(dep):
        return {
            "name": dep.name,
            "version": dep.version,
            "specified_version": dep.specified_version,
            "is_direct": dep.is_direct,
            "is_dev": dep.is_dev,
            "dependencies": [d.name for d in dep.dependencies],
        }
    
    data = {
        "project": {
            "name": result.project_path.name,
            "path": str(result.project_path),
            "type": result.project_type.value,
            "indicators": result.indicators,
        },
        "dependencies": {
            "direct": {name: dep_to_dict(dep) for name, dep in result.direct_dependencies.items()},
            "all": {name: dep_to_dict(dep) for name, dep in result.all_dependencies.items()},
            "dev": {name: dep_to_dict(dep) for name, dep in result.dev_dependencies.items()},
        },
        "issues": {
            "circular_dependencies": [
                {"path": cd.path, "severity": cd.severity}
                for cd in result.circular_dependencies
            ],
            "ghost_dependencies": [
                {
                    "name": gd.name,
                    "used_in": [str(p) for p in gd.used_in],
                    "severity": gd.severity,
                }
                for gd in result.ghost_dependencies
            ],
            "version_conflicts": [
                {"name": vc.name, "versions": list(vc.versions.keys()), "severity": vc.severity}
                for vc in result.version_conflicts
            ],
        },
    }
    
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def main():
    cli()


if __name__ == "__main__":
    main()
