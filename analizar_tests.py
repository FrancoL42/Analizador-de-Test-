#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import re
import json
from pathlib import Path
from collections import defaultdict
from dataclasses import dataclass, asdict, field
from typing import List, Dict
import argparse


@dataclass
class UseCase:
    name: str
    class_name: str
    file_path: str
    module: str
    domain: str
    methods: List[str]
    business_impact: str = "MEDIO"
    has_unit_tests: bool = False
    has_integration_tests: bool = False
    unit_test_files: List[str] = field(default_factory=list)
    integration_test_files: List[str] = field(default_factory=list)
    test_coverage_detail: Dict = field(default_factory=dict)


@dataclass
class TestFile:
    file_path: str
    test_type: str
    tested_class: str
    test_methods: List[str]
    covered_scenarios: List[str] = field(default_factory=list)


class JavaTestAnalyzer:
    
    def __init__(self, project_path: str):
        self.project_path = Path(project_path)
        self.use_cases = {}
        self.test_files = []
        
        self.high_impact_keywords = [
            'Order', 'Checkout', 'Payment', 'MercadoPago', 
            'Auth', 'Invoice', 'Stock', 'Webhook'
        ]
    
    def is_test_directory(self, path):
        return 'test' in path.parts
    
    def extract_domain(self, file_path, class_name):
        path_str = str(file_path)
        
        if 'orchestrator' in path_str.lower():
            parts = file_path.parts
            for i, part in enumerate(parts):
                if part.lower() == 'orchestrator' and i + 1 < len(parts):
                    return parts[i + 1]
            return 'orchestrator'
        
        elif 'business' in path_str.lower():
            parts = file_path.parts
            for i, part in enumerate(parts):
                if part.lower() == 'business' and i + 1 < len(parts):
                    return parts[i + 1]
            return 'business'
        
        elif 'controllers' in path_str.lower():
            parts = file_path.parts
            for i, part in enumerate(parts):
                if part.lower() == 'controllers' and i + 1 < len(parts):
                    return parts[i + 1]
            return 'controllers'
        
        return 'other'
    
    def assess_business_impact(self, class_name, file_path):
        for keyword in self.high_impact_keywords:
            if keyword in class_name:
                return "ALTO"
        
        if 'Controller' in class_name or 'Orchestrator' in class_name:
            return "ALTO"
        
        if 'Service' in class_name:
            return "MEDIO"
        
        return "BAJO"
    
    def extract_module_name(self, file_path):
        path_str = str(file_path)
        
        if 'orchestrator' in path_str.lower():
            parts = file_path.parts
            for i, part in enumerate(parts):
                if part.lower() == 'orchestrator' and i + 1 < len(parts):
                    return f"orchestrator.{parts[i + 1]}"
            return "orchestrator"
        
        elif 'business' in path_str.lower():
            parts = file_path.parts
            for i, part in enumerate(parts):
                if part.lower() == 'business' and i + 1 < len(parts):
                    subparts = []
                    for j in range(i + 1, min(i + 3, len(parts) - 1)):
                        subparts.append(parts[j])
                    return f"business.{'.'.join(subparts)}"
            return "business"
        
        elif 'controllers' in path_str.lower():
            parts = file_path.parts
            for i, part in enumerate(parts):
                if part.lower() == 'controllers' and i + 1 < len(parts):
                    return f"controllers.{parts[i + 1]}"
            return "controllers"
        
        return 'unknown'
    
    def extract_class_info(self, file_path):
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            
            class_match = re.search(r'(?:public\s+)?class\s+(\w+)', content)
            class_name = class_match.group(1) if class_match else file_path.stem
            
            method_pattern = r'public\s+(?:[\w<>\[\]]+\s+)+(\w+)\s*\([^)]*\)'
            methods = re.findall(method_pattern, content)
            
            return class_name, methods, content
        except Exception as e:
            print(f"Error leyendo {file_path}: {e}")
            return file_path.stem, [], ""
    
    def analyze_test_scenarios(self, content):
        scenarios = []
        
        if re.search(r'success|Success|happy|Happy|valid|Valid', content):
            scenarios.append("Happy path")
        if re.search(r'error|Error|exception|Exception|invalid|Invalid', content):
            scenarios.append("Error cases")
        if re.search(r'null|Null|empty|Empty|edge|Edge', content):
            scenarios.append("Edge cases")
        
        return scenarios if scenarios else ["Basic scenarios"]
    
    def is_use_case_file(self, file_path):
        if self.is_test_directory(file_path):
            return False
        
        file_str = str(file_path)
        
        if re.search(r'Repository\.java$', file_str):
            return False
        if re.search(r'DTO\.java$', file_str):
            return False
        if re.search(r'Entity\.java$', file_str):
            return False
        if re.search(r'Model\.java$', file_str):
            return False
        if re.search(r'Config\.java$', file_str):
            return False
        
        if re.search(r'orchestrator.*\.java$', file_str):
            return True
        if re.search(r'business.*Service\.java$', file_str):
            return True
        if re.search(r'business.*Handler\.java$', file_str):
            return True
        if re.search(r'controllers.*Controller\.java$', file_str):
            return True
        if re.search(r'business.*Facade\.java$', file_str):
            return True
        
        return False
    
    def is_test_file(self, file_path):
        if not self.is_test_directory(file_path):
            return False, None
        
        file_str = str(file_path)
        
        if re.search(r'IT\.java$', file_str):
            return True, 'integration'
        if re.search(r'IntegrationTest\.java$', file_str):
            return True, 'integration'
        if re.search(r'Test\.java$', file_str):
            return True, 'unit'
        if re.search(r'Tests\.java$', file_str):
            return True, 'unit'
        
        return False, None
    
    def extract_tested_class(self, test_file_path, content):
        filename = test_file_path.stem
        
        inject_pattern = r'@InjectMocks[^;]*?(\w+(?:Service|Handler|Controller|Orchestrator))'
        inject_matches = re.findall(inject_pattern, content, re.DOTALL)
        if inject_matches:
            return inject_matches[0]
        
        import_pattern = r'import\s+com\.Byron\.backoffice_service\.business\.\w+\.(?:service\.)?(\w+);'
        imports = re.findall(import_pattern, content)
        for imp in imports:
            if any(suffix in imp for suffix in ['Service', 'Handler', 'Controller', 'Orchestrator']):
                return imp
        
        orchestrator_pattern = r'import\s+com\.Byron\.backoffice_service\.orchestrator\.\w+\.(\w+);'
        orch_imports = re.findall(orchestrator_pattern, content)
        if orch_imports:
            return orch_imports[0]
        
        for suffix in ['Test', 'Tests', 'IT', 'IntegrationTest']:
            if filename.endswith(suffix):
                base_name = filename[:-len(suffix)]
                if base_name and not any(s in base_name for s in ['Service', 'Handler', 'Controller', 'Orchestrator']):
                    possible_names = [
                        base_name + 'Handler',
                        base_name + 'Service',
                        base_name + 'ServiceHandler',
                        base_name + 'Controller',
                        base_name + 'Orchestrator',
                        base_name
                    ]
                    return possible_names
                return base_name
        
        return filename
    
    def scan_project(self):
        print(f"Escaneando proyecto en: {self.project_path}")
        
        for java_file in self.project_path.rglob('*.java'):
            if self.is_use_case_file(java_file):
                class_name, methods, content = self.extract_class_info(java_file)
                module = self.extract_module_name(java_file)
                domain = self.extract_domain(java_file, class_name)
                impact = self.assess_business_impact(class_name, java_file)
                
                use_case = UseCase(
                    name=class_name,
                    class_name=class_name,
                    file_path=str(java_file.relative_to(self.project_path)),
                    module=module,
                    domain=domain,
                    methods=methods,
                    business_impact=impact
                )
                
                self.use_cases[class_name] = use_case
        
        print(f"Encontrados {len(self.use_cases)} casos de uso")
        
        for java_file in self.project_path.rglob('*.java'):
            is_test, test_type = self.is_test_file(java_file)
            
            if is_test:
                try:
                    with open(java_file, 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read()
                    
                    tested_class = self.extract_tested_class(java_file, content)
                    
                    test_method_pattern = r'@Test\s+(?:public\s+)?void\s+(\w+)\s*\('
                    test_methods = re.findall(test_method_pattern, content)
                    
                    scenarios = self.analyze_test_scenarios(content)
                    
                    test_file = TestFile(
                        file_path=str(java_file.relative_to(self.project_path)),
                        test_type=test_type,
                        tested_class=tested_class,
                        test_methods=test_methods,
                        covered_scenarios=scenarios
                    )
                    
                    self.test_files.append(test_file)
                    
                except Exception as e:
                    print(f"Error procesando test {java_file}: {e}")
        
        print(f"Encontrados {len(self.test_files)} archivos de test")
    
    def link_tests_to_use_cases(self):
        for test_file in self.test_files:
            tested_class = test_file.tested_class
            
            if isinstance(tested_class, list):
                for possible_name in tested_class:
                    if possible_name in self.use_cases:
                        tested_class = possible_name
                        break
                else:
                    tested_class = tested_class[0] if tested_class else "Unknown"
            
            if tested_class in self.use_cases:
                use_case = self.use_cases[tested_class]
                
                if test_file.test_type == 'unit':
                    use_case.has_unit_tests = True
                    use_case.unit_test_files.append(test_file.file_path)
                else:
                    use_case.has_integration_tests = True
                    use_case.integration_test_files.append(test_file.file_path)
                
                if test_file.test_type not in use_case.test_coverage_detail:
                    use_case.test_coverage_detail[test_file.test_type] = {
                        'test_count': 0,
                        'scenarios': set(),
                        'tested_methods': set()
                    }
                
                use_case.test_coverage_detail[test_file.test_type]['test_count'] += len(test_file.test_methods)
                use_case.test_coverage_detail[test_file.test_type]['scenarios'].update(test_file.covered_scenarios)
                
                for test_method in test_file.test_methods:
                    method_name = test_method.replace('test_', '').replace('test', '').replace('Test', '')
                    if method_name:
                        use_case.test_coverage_detail[test_file.test_type]['tested_methods'].add(method_name)
    
    def get_untested_methods_count(self, use_case):
        total_methods = len(use_case.methods)
        
        if total_methods == 0:
            return 0
        
        tested_methods = set()
        for test_type in use_case.test_coverage_detail.values():
            tested_methods.update(test_type.get('tested_methods', set()))
        
        if not use_case.has_unit_tests and not use_case.has_integration_tests:
            return total_methods
        
        if len(tested_methods) == 0 and (use_case.has_unit_tests or use_case.has_integration_tests):
            return max(0, total_methods // 2)
        
        untested = 0
        for method in use_case.methods:
            method_lower = method.lower()
            is_tested = any(tested.lower() in method_lower or method_lower in tested.lower() 
                          for tested in tested_methods)
            if not is_tested:
                untested += 1
        
        return untested
    
    def analyze_gaps(self):
        gaps = {
            'sin_tests': [],
            'solo_unitarios': [],
            'solo_integracion': [],
            'completo': [],
            'criticos_sin_tests': [],
            'necesitan_casos_borde': [],
        }
        
        for use_case in self.use_cases.values():
            if not use_case.has_unit_tests and not use_case.has_integration_tests:
                gaps['sin_tests'].append(use_case)
                if use_case.business_impact == "ALTO":
                    gaps['criticos_sin_tests'].append(use_case)
            elif use_case.has_unit_tests and not use_case.has_integration_tests:
                gaps['solo_unitarios'].append(use_case)
            elif use_case.has_integration_tests and not use_case.has_unit_tests:
                gaps['solo_integracion'].append(use_case)
            else:
                gaps['completo'].append(use_case)
        
        return gaps
    
    def _group_by_domain(self):
        by_domain = defaultdict(list)
        for uc in self.use_cases.values():
            by_domain[uc.domain].append(uc)
        return dict(by_domain)
    
    def _percentage(self, part, total):
        return int((part / total * 100)) if total > 0 else 0
    
    def _get_date(self):
        from datetime import datetime
        return datetime.now().strftime("%Y-%m-%d")
    
    def _estimate_effort(self, use_case):
        methods = len(use_case.methods)
        if methods > 10:
            return "3-5"
        elif methods > 5:
            return "2-3"
        else:
            return "1-2"
    
    def generate_pdf_report(self, output_file='test_coverage_report.pdf'):
        try:
            from reportlab.lib import colors
            from reportlab.lib.pagesizes import letter
            from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
            from reportlab.lib.units import inch
            from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak
            from reportlab.lib.enums import TA_CENTER
        except ImportError:
            print("reportlab not installed. Install with: pip install reportlab")
            print("Generating Markdown report instead...")
            self.generate_report(output_file.replace('.pdf', '.md'))
            return
        
        gaps = self.analyze_gaps()
        
        doc = SimpleDocTemplate(output_file, pagesize=letter, rightMargin=50, leftMargin=50, topMargin=50, bottomMargin=50)
        
        styles = getSampleStyleSheet()
        title_style = ParagraphStyle('CustomTitle', parent=styles['Heading1'], fontSize=24, textColor=colors.HexColor('#1a1a1a'), spaceAfter=30, alignment=TA_CENTER)
        heading_style = ParagraphStyle('CustomHeading', parent=styles['Heading2'], fontSize=16, textColor=colors.HexColor('#2c3e50'), spaceAfter=12, spaceBefore=12)
        normal_style = styles['Normal']
        
        story = []
        
        story.append(Paragraph("Test Coverage Report", title_style))
        story.append(Paragraph(f"<b>Project:</b> {self.project_path.name} | <b>Date:</b> {self._get_date()}", normal_style))
        story.append(Spacer(1, 20))
        
        story.append(Paragraph("Executive Summary", heading_style))
        total = len(self.use_cases)
        
        summary_data = [
            ['Metric', 'Count', 'Percentage'],
            ['Total use cases', str(total), '100%'],
            ['Complete coverage', str(len(gaps['completo'])), f"{self._percentage(len(gaps['completo']), total)}%"],
            ['Unit tests only', str(len(gaps['solo_unitarios'])), f"{self._percentage(len(gaps['solo_unitarios']), total)}%"],
            ['No tests', str(len(gaps['sin_tests'])), f"{self._percentage(len(gaps['sin_tests']), total)}%"],
            ['Critical without tests', str(len(gaps['criticos_sin_tests'])), f"{self._percentage(len(gaps['criticos_sin_tests']), total)}%"],
        ]
        
        summary_table = Table(summary_data, colWidths=[3*inch, 1.5*inch, 1.5*inch])
        summary_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#34495e')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 12),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ]))
        story.append(summary_table)
        story.append(Spacer(1, 20))
        
        story.append(Paragraph("Coverage by Domain", heading_style))
        by_domain = self._group_by_domain()
        
        domain_data = [['Domain', 'Total', 'No Tests', '%']]
        for domain, use_cases in sorted(by_domain.items()):
            without_tests = sum(1 for uc in use_cases if not uc.has_unit_tests and not uc.has_integration_tests)
            pct = self._percentage(without_tests, len(use_cases))
            domain_data.append([domain, str(len(use_cases)), str(without_tests), f"{pct}%"])
        
        domain_table = Table(domain_data, colWidths=[3*inch, 1.2*inch, 1.3*inch, 1*inch])
        domain_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2980b9')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ]))
        story.append(domain_table)
        story.append(Spacer(1, 20))
        
        story.append(Paragraph("Critical Gaps (TOP 10)", heading_style))
        
        if gaps['criticos_sin_tests']:
            critical_data = [['Use Case', 'Domain', 'Methods', 'Untested']]
            for uc in sorted(gaps['criticos_sin_tests'], key=lambda x: len(x.methods), reverse=True)[:10]:
                untested = self.get_untested_methods_count(uc)
                critical_data.append([uc.name, uc.domain, str(len(uc.methods)), str(untested)])
            
            critical_table = Table(critical_data, colWidths=[2.2*inch, 1.8*inch, 1*inch, 1.2*inch])
            critical_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#e74c3c')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 9),
                ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ]))
            story.append(critical_table)
        else:
            story.append(Paragraph("No critical cases without tests.", normal_style))
        
        story.append(PageBreak())
        
        story.append(Paragraph("Action Plan", heading_style))
        story.append(Paragraph("<b>Phase 1: Critical Cases (Immediate)</b>", normal_style))
        story.append(Spacer(1, 10))
        
        if gaps['criticos_sin_tests']:
            phase1_data = [['#', 'Use Case', 'Methods', 'Untested', 'Effort']]
            for i, uc in enumerate(sorted(gaps['criticos_sin_tests'], key=lambda x: len(x.methods), reverse=True)[:5], 1):
                untested = self.get_untested_methods_count(uc)
                phase1_data.append([str(i), uc.name, str(len(uc.methods)), str(untested), f"{self._estimate_effort(uc)} days"])
            
            phase1_table = Table(phase1_data, colWidths=[0.4*inch, 2.3*inch, 0.9*inch, 1.2*inch, 1.2*inch])
            phase1_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#27ae60')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 9),
                ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ]))
            story.append(phase1_table)
        
        doc.build(story)
        print(f"\nPDF report generated: {output_file}")
    
    def generate_report(self, output_file='test_coverage_report.md'):
        gaps = self.analyze_gaps()
        
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write("# Test Coverage Report\n\n")
            f.write(f"**Project:** {self.project_path.name} | **Date:** {self._get_date()}\n\n")
            
            f.write("## Executive Summary\n\n")
            total = len(self.use_cases)
            f.write(f"- Total use cases: **{total}**\n")
            f.write(f"- Complete coverage: **{len(gaps['completo'])}** ({self._percentage(len(gaps['completo']), total)}%)\n")
            f.write(f"- Unit tests only: **{len(gaps['solo_unitarios'])}** ({self._percentage(len(gaps['solo_unitarios']), total)}%)\n")
            f.write(f"- No tests: **{len(gaps['sin_tests'])}** ({self._percentage(len(gaps['sin_tests']), total)}%)\n")
            f.write(f"- Critical without tests: **{len(gaps['criticos_sin_tests'])}**\n\n")
            
            f.write("## Coverage by Domain\n\n")
            by_domain = self._group_by_domain()
            f.write("| Domain | Total | No Tests | % |\n")
            f.write("|--------|-------|----------|---|\n")
            for domain, use_cases in sorted(by_domain.items()):
                without_tests = sum(1 for uc in use_cases if not uc.has_unit_tests and not uc.has_integration_tests)
                pct = self._percentage(without_tests, len(use_cases))
                f.write(f"| {domain} | {len(use_cases)} | {without_tests} | {pct}% |\n")
            f.write("\n")
            
            f.write("## Critical Gaps\n\n")
            if gaps['criticos_sin_tests']:
                f.write("| Use Case | Domain | Total Methods | Untested |\n")
                f.write("|----------|--------|---------------|----------|\n")
                for uc in sorted(gaps['criticos_sin_tests'], key=lambda x: len(x.methods), reverse=True)[:10]:
                    untested = self.get_untested_methods_count(uc)
                    f.write(f"| {uc.name} | {uc.domain} | {len(uc.methods)} | {untested} |\n")
                f.write("\n")
            
            f.write("## Cases Without Tests\n\n")
            if gaps['sin_tests']:
                f.write("| Use Case | Domain | Total Methods | Impact |\n")
                f.write("|----------|--------|---------------|--------|\n")
                for uc in sorted(gaps['sin_tests'], key=lambda x: (x.business_impact, len(x.methods)), reverse=True)[:20]:
                    f.write(f"| {uc.name} | {uc.domain} | {len(uc.methods)} | {uc.business_impact} |\n")
                if len(gaps['sin_tests']) > 20:
                    f.write(f"\n*... and {len(gaps['sin_tests']) - 20} more cases without tests*\n")
                f.write("\n")
            
            f.write("## Action Plan\n\n")
            f.write("### Phase 1: Critical Cases\n\n")
            if gaps['criticos_sin_tests']:
                for i, uc in enumerate(sorted(gaps['criticos_sin_tests'], key=lambda x: len(x.methods), reverse=True)[:5], 1):
                    untested = self.get_untested_methods_count(uc)
                    f.write(f"{i}. **{uc.name}** ({uc.domain})\n")
                    f.write(f"   - Total methods: {len(uc.methods)}\n")
                    f.write(f"   - Untested methods: {untested}\n")
                    f.write(f"   - Estimated effort: {self._estimate_effort(uc)} days\n\n")
        
        print(f"\nReport generated: {output_file}")
    
    def generate_json_report(self, output_file='test_coverage_report.json'):
        gaps = self.analyze_gaps()
        
        report = {
            'summary': {
                'total_use_cases': len(self.use_cases),
                'complete_coverage': len(gaps['completo']),
                'unit_only': len(gaps['solo_unitarios']),
                'no_tests': len(gaps['sin_tests']),
                'critical_without_tests': len(gaps['criticos_sin_tests'])
            },
            'gaps': {
                'criticos_sin_tests': [asdict(uc) for uc in gaps['criticos_sin_tests']]
            }
        }
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False, default=str)
        
        print(f"JSON report generated: {output_file}")


def main():
    parser = argparse.ArgumentParser(description='Java Test Coverage Analyzer')
    parser.add_argument('project_path', help='Path to Java project')
    parser.add_argument('--output', '-o', default='test_coverage_report.pdf', help='Output file')
    parser.add_argument('--format', '-f', choices=['pdf', 'md', 'both'], default='pdf', help='Report format')
    parser.add_argument('--json', action='store_true', help='Generate JSON report')
    args = parser.parse_args()
    
    analyzer = JavaTestAnalyzer(args.project_path)
    analyzer.scan_project()
    analyzer.link_tests_to_use_cases()
    
    if args.format == 'pdf' or args.format == 'both':
        pdf_output = args.output if args.output.endswith('.pdf') else 'test_coverage_report.pdf'
        analyzer.generate_pdf_report(pdf_output)
    
    if args.format == 'md' or args.format == 'both':
        md_output = args.output if args.output.endswith('.md') else 'test_coverage_report.md'
        analyzer.generate_report(md_output)
    
    if args.json:
        analyzer.generate_json_report('test_coverage_report.json')

if __name__ == '__main__':
    main()