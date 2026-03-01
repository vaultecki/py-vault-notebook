# Copyright [2025] [ecki]
# SPDX-License-Identifier: Apache-2.0

"""
Graph visualization for wiki structure using HTML/JavaScript.
"""
import logging
import json
import os
import re
from typing import List, Dict, Set, Tuple

logger = logging.getLogger(__name__)


def generate_graph_html(files: List[str], project_path: str) -> str:
    """
    Generate HTML with D3.js force-directed graph visualization.
    
    Args:
        files: List of file paths in the project
        project_path: Base path of the project
        
    Returns:
        Complete HTML page with graph visualization
    """
    # Analyze wiki structure to get nodes and links
    nodes, links = _analyze_wiki_links(files, project_path)
    
    # Convert to JSON
    nodes_json = json.dumps(nodes)
    links_json = json.dumps(links)
    
    html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>Wiki Graph</title>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/d3/7.8.5/d3.min.js"></script>
    <style>
        body {{
            margin: 0;
            padding: 20px;
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
            background: #f5f5f5;
        }}
        
        #graph-container {{
            width: 100%;
            height: calc(100vh - 120px);
            background: white;
            border-radius: 8px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
            position: relative;
        }}
        
        .controls {{
            margin-bottom: 15px;
            padding: 15px;
            background: white;
            border-radius: 8px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
        }}
        
        .controls h2 {{
            margin: 0 0 10px 0;
            font-size: 20px;
            color: #333;
        }}
        
        .controls p {{
            margin: 5px 0;
            color: #666;
            font-size: 13px;
        }}
        
        .node {{
            cursor: pointer;
            stroke: #fff;
            stroke-width: 2px;
        }}
        
        .node.index {{
            fill: #e74c3c;
        }}
        
        .node.document {{
            fill: #3498db;
        }}
        
        .node.orphan {{
            fill: #95a5a6;
        }}
        
        .node:hover {{
            stroke: #000;
            stroke-width: 3px;
        }}
        
        .link {{
            stroke: #999;
            stroke-opacity: 0.6;
            stroke-width: 1.5px;
        }}
        
        .label {{
            font-size: 11px;
            pointer-events: none;
            text-anchor: middle;
            fill: #333;
        }}
        
        .tooltip {{
            position: absolute;
            padding: 10px;
            background: rgba(0, 0, 0, 0.8);
            color: white;
            border-radius: 5px;
            pointer-events: none;
            font-size: 12px;
            display: none;
            z-index: 1000;
        }}
        
        .legend {{
            position: absolute;
            top: 20px;
            right: 20px;
            background: white;
            padding: 15px;
            border-radius: 5px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
            font-size: 12px;
        }}
        
        .legend-item {{
            margin: 8px 0;
            display: flex;
            align-items: center;
        }}
        
        .legend-color {{
            width: 16px;
            height: 16px;
            border-radius: 50%;
            margin-right: 8px;
        }}
    </style>
</head>
<body>
    <div class="controls">
        <h2>📊 Wiki Graph Visualisierung</h2>
        <p>Interaktive Darstellung der Wiki-Struktur. Ziehen Sie Knoten um die Ansicht zu ändern.</p>
        <p><strong>Knoten:</strong> {len(nodes)} Seiten | <strong>Verbindungen:</strong> {len(links)} Links</p>
    </div>
    
    <div id="graph-container">
        <div class="legend">
            <div class="legend-item">
                <div class="legend-color" style="background: #e74c3c;"></div>
                <span>Index-Seiten</span>
            </div>
            <div class="legend-item">
                <div class="legend-color" style="background: #3498db;"></div>
                <span>Normale Seiten</span>
            </div>
            <div class="legend-item">
                <div class="legend-color" style="background: #95a5a6;"></div>
                <span>Verwaiste Seiten</span>
            </div>
        </div>
    </div>
    <div class="tooltip" id="tooltip"></div>
    
    <script>
        const nodes = {nodes_json};
        const links = {links_json};
        
        const container = document.getElementById('graph-container');
        const width = container.clientWidth;
        const height = container.clientHeight;
        
        const svg = d3.select('#graph-container')
            .append('svg')
            .attr('width', width)
            .attr('height', height);
        
        const g = svg.append('g');
        
        // Zoom behavior
        const zoom = d3.zoom()
            .scaleExtent([0.1, 4])
            .on('zoom', (event) => {{
                g.attr('transform', event.transform);
            }});
        
        svg.call(zoom);
        
        // Force simulation
        const simulation = d3.forceSimulation(nodes)
            .force('link', d3.forceLink(links)
                .id(d => d.id)
                .distance(100))
            .force('charge', d3.forceManyBody().strength(-300))
            .force('center', d3.forceCenter(width / 2, height / 2))
            .force('collision', d3.forceCollide().radius(30));
        
        // Links
        const link = g.append('g')
            .selectAll('line')
            .data(links)
            .enter()
            .append('line')
            .attr('class', 'link');
        
        // Nodes
        const node = g.append('g')
            .selectAll('circle')
            .data(nodes)
            .enter()
            .append('circle')
            .attr('class', d => `node ${{d.type}}`)
            .attr('r', d => d.type === 'index' ? 12 : 8)
            .call(d3.drag()
                .on('start', dragstarted)
                .on('drag', dragged)
                .on('end', dragended))
            .on('click', clicked)
            .on('mouseover', showTooltip)
            .on('mouseout', hideTooltip);
        
        // Labels
        const label = g.append('g')
            .selectAll('text')
            .data(nodes)
            .enter()
            .append('text')
            .attr('class', 'label')
            .attr('dy', -15)
            .text(d => d.label);
        
        simulation.on('tick', () => {{
            link
                .attr('x1', d => d.source.x)
                .attr('y1', d => d.source.y)
                .attr('x2', d => d.target.x)
                .attr('y2', d => d.target.y);
            
            node
                .attr('cx', d => d.x)
                .attr('cy', d => d.y);
            
            label
                .attr('x', d => d.x)
                .attr('y', d => d.y);
        }});
        
        function dragstarted(event, d) {{
            if (!event.active) simulation.alphaTarget(0.3).restart();
            d.fx = d.x;
            d.fy = d.y;
        }}
        
        function dragged(event, d) {{
            d.fx = event.x;
            d.fy = event.y;
        }}
        
        function dragended(event, d) {{
            if (!event.active) simulation.alphaTarget(0);
            d.fx = null;
            d.fy = null;
        }}
        
        function clicked(event, d) {{
            console.log('Clicked:', d.id);
            // In actual implementation, this would navigate to the page
            alert('Navigate to: ' + d.id);
        }}
        
        function showTooltip(event, d) {{
            const tooltip = document.getElementById('tooltip');
            tooltip.style.display = 'block';
            tooltip.style.left = (event.pageX + 10) + 'px';
            tooltip.style.top = (event.pageY - 28) + 'px';
            tooltip.innerHTML = `
                <strong>${{d.label}}</strong><br>
                Eingehende Links: ${{d.inLinks}}<br>
                Ausgehende Links: ${{d.outLinks}}
            `;
        }}
        
        function hideTooltip() {{
            document.getElementById('tooltip').style.display = 'none';
        }}
    </script>
</body>
</html>"""
    
    return html


def _analyze_wiki_links(files: List[str], project_path: str) -> Tuple[List[Dict], List[Dict]]:
    """
    Analyze wiki to extract nodes and links for graph.
    
    Args:
        files: List of file paths
        project_path: Base project path
        
    Returns:
        Tuple of (nodes, links) as lists of dicts
    """
    # Only process adoc files
    adoc_files = [f for f in files if f.endswith(('.adoc', '.asciidoc'))]
    
    # Track all links
    file_links: Dict[str, Set[str]] = {}  # file -> set of linked files
    all_targets: Set[str] = set()
    
    for file in adoc_files:
        file_path = os.path.join(project_path, file)
        file_links[file] = set()
        
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            
            # Find all links
            links = re.findall(r'link:([^\[]+)\[', content)
            
            for link in links:
                link = link.strip()
                
                # Skip external links
                if link.startswith(('http://', 'https://', 'ftp://', 'mailto:')):
                    continue
                
                # Calculate target path
                current_dir = os.path.dirname(file)
                if current_dir:
                    target = os.path.normpath(os.path.join(current_dir, link))
                else:
                    target = os.path.normpath(link)
                
                target = target.replace(os.path.sep, '/')
                
                # Only include adoc files
                if target.endswith(('.adoc', '.asciidoc')):
                    file_links[file].add(target)
                    all_targets.add(target)
        
        except Exception as e:
            logger.error(f"Error analyzing {file}: {e}")
    
    # Build nodes
    nodes = []
    incoming_links: Dict[str, int] = {}  # Count incoming links
    
    for file in adoc_files:
        normalized = file.replace(os.path.sep, '/')
        incoming_links[normalized] = 0
    
    # Count incoming links
    for source, targets in file_links.items():
        for target in targets:
            if target in incoming_links:
                incoming_links[target] += 1
    
    # Create nodes
    for file in adoc_files:
        normalized = file.replace(os.path.sep, '/')
        label = os.path.basename(file).replace('.adoc', '').replace('.asciidoc', '')
        
        # Determine node type
        if file.endswith(('index.adoc', 'index.asciidoc')):
            node_type = 'index'
        elif incoming_links.get(normalized, 0) == 0:
            node_type = 'orphan'
        else:
            node_type = 'document'
        
        nodes.append({
            'id': normalized,
            'label': label,
            'type': node_type,
            'inLinks': incoming_links.get(normalized, 0),
            'outLinks': len(file_links.get(file, set()))
        })
    
    # Build links
    links = []
    for source, targets in file_links.items():
        source_normalized = source.replace(os.path.sep, '/')
        for target in targets:
            # Only create link if both nodes exist
            if target in [n['id'] for n in nodes]:
                links.append({
                    'source': source_normalized,
                    'target': target
                })
    
    return nodes, links
