#! /usr/bin/env python3
'''
Build a standalone interactive HTML website from the GameEduDB contents
'''

# imports
from pathlib import Path
from sys import argv
import json
import re
import html

# constants
PROGRAM_FIELD_ORDER = [
    'description',
    'institution_id',
    'department_id',
    'abbreviation',
    'program_code',
    'degree',
    'level',
    'length',
    'total_credits',
    'credit_system',
]
COURSE_FIELD_ORDER = [
    'course_code',
    'description',
    'institution_id',
    'department_id',
    'credits',
    'credit_system',
]
INSTITUTION_FIELD_ORDER = [
    'description',
    'location',
    'abbreviation',
    'url',
]
DEPARTMENT_FIELD_ORDER = [
    'description',
    'institution_id',
    'abbreviation',
    'url',
]
COURSE_ID_KEYS = {
    'course_ids_core': 'Core',
    'course_ids_path': 'Path',
    'course_ids_elective': 'Elective',
}
TRANSLATE = {
    'abbreviation': 'Abbreviation',
    'course_code': 'Course Code',
    'credits': 'Credits',
    'credit_system': 'Credit/Unit System',
    'degree': 'Degree Type',
    'department_id': 'Department',
    'description': 'Description',
    'institution_id': 'Institution',
    'length': 'Expected Length (years)',
    'level': 'Academic Level',
    'location': 'Location',
    'program_code': 'Program Code',
    'total_credits': 'Total Credits/Units',
    'url': 'Official Website',
}

# sorting helpers
def natural_sort_key(value):
    return [int(part) if part.isdigit() else part.casefold() for part in re.split(r'(\d+)', str(value))]

def entity_sort_key(entry_id, data, entity_type):
    return natural_sort_key(data[entity_type][entry_id]['name'][0]), entry_id.casefold(), entry_id

def course_code_sort_key(course_id, data):
    course_data = data['courses'][course_id]
    code = course_data.get('course_code', [''])[0]
    return tuple(
        tuple((0, int(part)) if part.isdigit() else (1, part.casefold()) for part in re.findall(r'\d+|\D+', component))
        for component in code.split()
    ), course_data['name'][0].casefold(), course_id.casefold(), course_id

def course_title(course_id, data):
    course_data = data['courses'][course_id]
    code = course_data.get('course_code', [''])[0]
    name = course_data['name'][0]
    return f'{code}: {name}' if code else name

def sort_course_ids(course_ids, data):
    # Topologically sort the complete prerequisite graph, using course code and name to break ties
    course_ids = set(course_ids)
    relevant_ids = prerequisite_closure(course_ids, data)
    indegree = {course_id: 0 for course_id in relevant_ids}
    dependents = {course_id: set() for course_id in relevant_ids}
    for course_id in relevant_ids:
        for prerequisite_id in data['courses'][course_id].get('prerequisite_course_ids', []):
            if prerequisite_id in relevant_ids:
                indegree[course_id] += 1
                dependents[prerequisite_id].add(course_id)
    available = sorted((course_id for course_id, degree in indegree.items() if degree == 0), key=lambda x: course_code_sort_key(x, data))
    ordered = []
    while available:
        course_id = available.pop(0)
        if course_id in course_ids:
            ordered.append(course_id)
        for dependent_id in sorted(dependents[course_id], key=lambda x: course_code_sort_key(x, data)):
            indegree[dependent_id] -= 1
            if indegree[dependent_id] == 0:
                available.append(dependent_id)
                available.sort(key=lambda x: course_code_sort_key(x, data))
    # Valid data is assumed; retain a deterministic fallback if a cycle exists
    if len(ordered) != len(course_ids):
        ordered.extend(sorted(course_ids - set(ordered), key=lambda x: course_code_sort_key(x, data)))
    return ordered

def prerequisite_closure(course_ids, data):
    included = set(course_ids)
    pending = list(course_ids)
    while pending:
        course_id = pending.pop()
        for prerequisite_id in data['courses'][course_id].get('prerequisite_course_ids', []):
            if prerequisite_id not in included:
                included.add(prerequisite_id)
                pending.append(prerequisite_id)
    return included

# content helpers
def display_value(key, values):
    if key == 'url':
        return ''
    if key.endswith('_id'):
        return ''
    if key in {'abbreviation'} or len(values) > 1:
        return '<div class="value-badges">' + ''.join(f'<span class="value-badge">{html.escape(value)}</span>' for value in values) + '</div>'
    return '<div class="metadata-value">' + '<br>'.join(html.escape(value) for value in values) + '</div>'

def metadata_html(entity_type, entity_id, data, fields):
    entity_data = data[entity_type][entity_id]
    ordered = [key for key in fields if key in entity_data and key not in {'name', 'description'}]
    remaining = [key for key in entity_data if key not in set(fields) | {'name', 'description', 'url', 'course_id', 'prerequisite_course_ids'} and not key.startswith('course_ids_')]
    remaining.sort(key=lambda key: (TRANSLATE.get(key, key.replace('_', ' ').title()).casefold(), key))
    keys = ordered + remaining
    if not keys:
        return ''
    out = '<section class="panel metadata-panel"><h2>Information</h2><div class="metadata-grid">'
    for key in keys:
        values = entity_data[key]
        label = TRANSLATE.get(key, key.replace('_', ' ').title())
        if key.endswith('_id'):
            target_type = 'institutions' if key == 'institution_id' else 'departments'
            target_id = values[0]
            value = entity_link(target_type, target_id, data)
        elif key == 'url':
            label = {'institutions': 'Official Institution Website', 'departments': 'Official Department Page'}.get(entity_type, 'Official Website')
            value = external_link(entity_data, label)
        else:
            value = display_value(key, values)
        if value:
            out += f'<div class="metadata-item"><div class="metadata-label">{html.escape(label)}</div>{value}</div>'
    out += '</div></section>'
    return out

def entity_link(entity_type, entity_id, data, label=None):
    name = label or data[entity_type][entity_id]['name'][0]
    return f'<a href="#{entity_type[:-1]}/{html.escape(entity_id, quote=True)}">{html.escape(name)}</a>'

def external_link(entity_data, label):
    if 'url' not in entity_data:
        return ''
    url = entity_data['url'][0]
    return f'<a class="external-link" href="{html.escape(url, quote=True)}" target="_blank" rel="noopener noreferrer">{html.escape(label)} ↗</a>'

def description_html(entity_data):
    if 'description' not in entity_data:
        return ''
    return '<div class="description">' + ''.join(f'<p>{html.escape(paragraph)}</p>' for paragraph in entity_data['description']) + '</div>'

def program_card(program_id, data, classifications=None):
    program = data['programs'][program_id]
    institution_id = program['institution_id'][0]
    out = f'<a class="entity-card program-card" href="#program/{html.escape(program_id, quote=True)}"><div class="card-title">{html.escape(program["name"][0])}</div>'
    out += f'<div class="card-subtitle">{html.escape(data["institutions"][institution_id]["name"][0])}</div>'
    if 'description' in program:
        out += f'<div class="card-description clamp">{" ".join(html.escape(value) for value in program["description"])}</div>'
    if classifications:
        out += '<div class="badges">' + ''.join(f'<span class="badge badge-{name.casefold()}">{name}</span>' for name in classifications) + '</div>'
    return out + '</a>'

def course_card(course_id, data, classifications=None):
    course = data['courses'][course_id]
    out = f'<a class="entity-card course-card" href="#course/{html.escape(course_id, quote=True)}"><div class="card-title">{html.escape(course_title(course_id, data))}</div>'
    if 'description' in course:
        out += f'<div class="card-description">{" ".join(html.escape(value) for value in course["description"])}</div>'
    if classifications:
        out += '<div class="badges">' + ''.join(f'<span class="badge badge-{name.casefold()}">{name}</span>' for name in classifications) + '</div>'
    return out + '</a>'

def build_website(data):
    institution_to_programs = {key: set() for key in data['institutions']}
    institution_to_departments = {key: set() for key in data['institutions']}
    institution_to_courses = {key: set() for key in data['institutions']}
    department_to_courses = {key: set() for key in data['departments']}
    department_to_programs = {key: set() for key in data['departments']}
    course_to_programs = {key: {} for key in data['courses']}
    for program_id, program in data['programs'].items():
        institution_to_programs[program['institution_id'][0]].add(program_id)
        if 'department_id' in program:
            department_to_programs[program['department_id'][0]].add(program_id)
        for key, label in COURSE_ID_KEYS.items():
            for course_id in program.get(key, []):
                course_to_programs[course_id].setdefault(program_id, set()).add(label)
    for department_id, department in data['departments'].items():
        institution_to_departments[department['institution_id'][0]].add(department_id)
    for course_id, course in data['courses'].items():
        institution_to_courses[course['institution_id'][0]].add(course_id)
        if 'department_id' in course:
            department_to_courses[course['department_id'][0]].add(course_id)
    entities = {}
    for entity_type in ['programs', 'institutions', 'departments', 'courses']:
        for entity_id, entity_data in data[entity_type].items():
            entities[f'{entity_type[:-1]}/{entity_id}'] = {
                'type': entity_type[:-1], 'id': entity_id,
                'name': entity_data['name'][0],
                'code': entity_data.get('course_code', [''])[0],
                'description': ' '.join(entity_data.get('description', [])),
                'institution': data['institutions'][entity_data['institution_id'][0]]['name'][0] if 'institution_id' in entity_data else '',
            }
    views = {}
    # Program views
    for program_id, program in data['programs'].items():
        institution_id = program['institution_id'][0]
        title = program['name'][0]
        body = f'<header class="entity-header"><div class="eyebrow">PROGRAM</div><h1>{html.escape(title)}</h1>{external_link(program, "Official Program Page")}{description_html(program)}</header>'
        body += metadata_html('programs', program_id, data, PROGRAM_FIELD_ORDER)
        required = set().union(*(set(program.get(key, [])) for key in COURSE_ID_KEYS))
        ordered_courses = sort_course_ids(required, data)
        if ordered_courses:
            body += '<section class="panel course-list"><div class="section-title-row"><h2>Courses</h2><div class="filters"><button class="filter active" data-filter="all">All</button><button class="filter" data-filter="core">Core</button><button class="filter" data-filter="path">Path</button><button class="filter" data-filter="elective">Elective</button></div></div><div class="cards">'
            for course_id in ordered_courses:
                classifications = [label for key, label in COURSE_ID_KEYS.items() if course_id in program.get(key, [])]
                card = course_card(course_id, data, classifications)
                body += f'<div class="filterable" data-classifications="{" ".join(value.casefold() for value in classifications)}">{card}</div>'
            body += '</div></section>'
        views[f'program/{program_id}'] = {'type': 'program', 'title': title, 'body': body}
    # Institution views
    for institution_id, institution in data['institutions'].items():
        title = institution['name'][0]
        body = f'<header class="entity-header"><div class="eyebrow">INSTITUTION</div><h1>{html.escape(title)}</h1>{description_html(institution)}</header>'
        body += metadata_html('institutions', institution_id, data, INSTITUTION_FIELD_ORDER)
        program_ids = sorted(institution_to_programs[institution_id], key=lambda x: entity_sort_key(x, data, 'programs'))
        if program_ids:
            body += '<section class="panel"><h2>Programs</h2><div class="cards">' + ''.join(program_card(x, data) for x in program_ids) + '</div></section>'
        department_ids = sorted(institution_to_departments[institution_id], key=lambda x: entity_sort_key(x, data, 'departments'))
        if department_ids:
            body += '<section class="panel"><h2>Departments</h2><div class="cards">'
            for department_id in department_ids:
                department = data['departments'][department_id]
                body += f'<a class="entity-card" href="#department/{html.escape(department_id, quote=True)}"><div class="card-title">{html.escape(department["name"][0])}</div>'
                if 'description' in department:
                    body += f'<div class="card-description clamp">{" ".join(html.escape(x) for x in department["description"])}</div>'
                body += '</a>'
            body += '</div></section>'
        course_ids = institution_to_courses[institution_id]
        ordered_courses = sort_course_ids(course_ids, data)
        if ordered_courses:
            body += '<section class="panel"><h2>Courses</h2><div class="cards">' + ''.join(course_card(x, data) for x in ordered_courses) + '</div></section>'
        views[f'institution/{institution_id}'] = {'type': 'institution', 'title': title, 'body': body}
    # Department views
    for department_id, department in data['departments'].items():
        title = department['name'][0]
        body = f'<header class="entity-header"><div class="eyebrow">DEPARTMENT</div><h1>{html.escape(title)}</h1>{description_html(department)}</header>'
        body += metadata_html('departments', department_id, data, DEPARTMENT_FIELD_ORDER)
        program_ids = sorted(department_to_programs[department_id], key=lambda x: entity_sort_key(x, data, 'programs'))
        if program_ids:
            body += '<section class="panel"><h2>Programs</h2><div class="cards">' + ''.join(program_card(x, data) for x in program_ids) + '</div></section>'
        course_ids = department_to_courses[department_id]
        ordered_courses = sort_course_ids(course_ids, data)
        if ordered_courses:
            body += '<section class="panel"><h2>Courses</h2><div class="cards">' + ''.join(course_card(x, data) for x in ordered_courses) + '</div></section>'
        views[f'department/{department_id}'] = {'type': 'department', 'title': title, 'body': body}
    # Course views
    for course_id, course in data['courses'].items():
        title = course_title(course_id, data)
        body = f'<header class="entity-header"><div class="eyebrow">COURSE</div><h1>{html.escape(title)}</h1>{external_link(course, "Official Course Catalog Entry")}{description_html(course)}</header>'
        body += metadata_html('courses', course_id, data, COURSE_FIELD_ORDER)
        prerequisite_ids = sorted(set(course.get('prerequisite_course_ids', [])), key=lambda x: course_code_sort_key(x, data))
        if prerequisite_ids:
            body += '<section class="panel"><h2>Prerequisites</h2><div class="compact-links">'
            for prerequisite_id in prerequisite_ids:
                body += f'<a class="compact-link" href="#course/{html.escape(prerequisite_id, quote=True)}">{html.escape(course_title(prerequisite_id, data))}</a>'
            body += '</div></section>'
        program_ids = sorted(course_to_programs[course_id], key=lambda x: entity_sort_key(x, data, 'programs'))
        if program_ids:
            body += '<section class="panel"><h2>Programs Offering This Course</h2><div class="cards">'
            for program_id in program_ids:
                body += program_card(program_id, data, sorted(course_to_programs[course_id][program_id]))
            body += '</div></section>'
        views[f'course/{course_id}'] = {'type': 'course', 'title': title, 'body': body}
    directory = '<div class="directory"><h1>Video Game Development Programs</h1><p class="intro">Explore programs, institutions, departments, and courses in video game development.</p><div class="cards">'
    for program_id in sorted(data['programs'], key=lambda x: entity_sort_key(x, data, 'programs')):
        directory += program_card(program_id, data)
    directory += '</div></div>'
    payload = json.dumps({'views': views, 'entities': entities}, ensure_ascii=False).replace('</', '<\\/')
    return HTML_TEMPLATE.replace('<!-- DIRECTORY -->', directory).replace('<!-- DATA -->', payload)

HTML_TEMPLATE = r'''<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="color-scheme" content="light dark"><title>GameEduDB</title>
<style>
:root{color-scheme:light;--bg:#f2f5fa;--surface:#fff;--surface-2:#f7f9fc;--text:#24334c;--muted:#64748b;--border:#e1e7ef;--accent:#426fa8;--shadow:0 2px 8px #1e293b0a}
:root[data-theme="dark"]{color-scheme:dark;--bg:#171c27;--surface:#202938;--surface-2:#283446;--text:#edf2f8;--muted:#aab7c8;--border:#39465a;--accent:#91b9ed;--shadow:0 2px 8px #0003}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--text);font:15px/1.55 system-ui,-apple-system,"Segoe UI",sans-serif}
a{color:var(--accent);text-decoration:none}a:hover{text-decoration:underline}.topbar{position:sticky;top:0;z-index:10;background:var(--surface);border-bottom:1px solid var(--border);box-shadow:var(--shadow)}.topbar-inner{max-width:1400px;margin:auto;padding:12px 24px;display:flex;align-items:center;gap:18px}.brand{font-weight:800;font-size:21px;color:var(--text);white-space:nowrap}.search{flex:1;min-width:80px;max-width:680px;margin:auto}.search input{width:100%;padding:10px 14px;border:1px solid var(--border);border-radius:9px;background:var(--surface-2);color:var(--text);font:inherit}.theme-toggle,.nav-button,.filter{border:1px solid var(--border);background:var(--surface-2);color:var(--text);border-radius:9px;padding:9px 12px;cursor:pointer;font:inherit}.theme-toggle{white-space:nowrap}.main{max-width:1400px;margin:0 auto;padding:20px 24px 64px}.breadcrumbs{display:flex;gap:8px;white-space:nowrap;overflow-x:auto;padding:2px 0 18px;color:var(--muted);font-size:13px}.breadcrumbs a{flex:none}.breadcrumbs .current{color:var(--text);font-weight:600}.view h1,.directory h1{font-size:clamp(26px,3vw,36px);line-height:1.2;margin:4px 0 10px}.intro,.description{color:var(--muted)}.description p{margin:8px 0}.entity-header{margin:4px 0 20px}.eyebrow{font-size:11px;font-weight:800;letter-spacing:.12em;color:var(--muted)}.external-link{display:inline-block;margin:4px 0 8px;font-size:13px;font-weight:650}.panel{background:var(--surface);border:1px solid var(--border);border-radius:13px;padding:20px;margin:16px 0;box-shadow:var(--shadow)}.panel h2{font-size:19px;margin:0 0 14px}.metadata-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:16px 28px}.metadata-label{font-size:12px;color:var(--muted);margin-bottom:3px}.metadata-value{font-weight:550}.value-badges,.badges{display:flex;flex-wrap:wrap;gap:6px}.value-badge,.badge{display:inline-block;padding:3px 9px;border-radius:20px;background:var(--surface-2);border:1px solid var(--border);font-size:12px}.badge-core{background:#dceafb;color:#24558c}.badge-path{background:#dff2e7;color:#246743}.badge-elective{background:#f3e8fb;color:#70418c}:root[data-theme="dark"] .badge-core{background:#244568;color:#c5defb}:root[data-theme="dark"] .badge-path{background:#214b38;color:#c5efd5}:root[data-theme="dark"] .badge-elective{background:#49345d;color:#ead4fa}.cards{display:grid;grid-template-columns:1fr;gap:10px}.entity-card{display:block;background:var(--surface-2);border:1px solid var(--border);border-radius:10px;padding:14px 16px;color:var(--text);transition:border-color .15s,transform .15s}.entity-card:hover{border-color:var(--accent);text-decoration:none;transform:translateY(-1px)}.card-title{font-weight:720;font-size:16px}.card-subtitle{font-size:13px;color:var(--muted);margin-top:1px}.card-description{font-size:13px;color:var(--muted);margin-top:7px}.program-card .card-description{display:-webkit-box;-webkit-box-orient:vertical;-webkit-line-clamp:3;overflow:hidden}.badges{margin-top:8px}.section-title-row{display:flex;justify-content:space-between;align-items:center;gap:12px;flex-wrap:wrap}.section-title-row h2{margin:0}.filters{display:flex;gap:6px;flex-wrap:wrap}.filter{font-size:12px;padding:6px 10px}.filter.active{background:var(--accent);color:white;border-color:var(--accent)}.compact-links{display:flex;flex-direction:column;gap:8px}.compact-link{display:block;padding:10px 12px;background:var(--surface-2);border:1px solid var(--border);border-radius:8px;font-weight:600}.directory>.cards{margin-top:20px}.directory .intro{max-width:850px}.search-results h2{font-size:16px;margin:24px 0 9px}.search-results .entity-card{margin-bottom:8px}.empty-state{text-align:center;padding:70px 20px;color:var(--muted)}.empty-state h2{color:var(--text)}.empty-state button{margin-top:12px}.hidden{display:none!important}
@media(min-width:900px){.program-card .card-description{-webkit-line-clamp:3}}
@media(min-width:600px) and (max-width:899px){.program-card .card-description{-webkit-line-clamp:4}}
@media(max-width:599px){.topbar-inner{padding:9px 12px;gap:9px;flex-wrap:wrap}.brand{font-size:18px}.search{order:3;flex-basis:100%;max-width:none}.theme-toggle{margin-left:auto;padding:7px 9px}.main{padding:14px 12px 44px}.breadcrumbs{margin-right:-12px;padding-bottom:13px}.panel{padding:15px;margin:12px 0}.metadata-grid{grid-template-columns:1fr;gap:12px}.program-card .card-description{-webkit-line-clamp:5}.card-title{font-size:15px}}
</style></head><body>
<header class="topbar"><div class="topbar-inner"><a class="brand" href="#">GameEduDB</a><div class="search"><input id="search" type="search" placeholder="Search programs, institutions, departments, and courses…" autocomplete="off" aria-label="Search GameEduDB"></div><button class="theme-toggle" id="theme-toggle" type="button">Dark mode</button></div></header>
<main class="main"><nav class="breadcrumbs" id="breadcrumbs" aria-label="Breadcrumbs"></nav><div id="directory" class="view"><!-- DIRECTORY --></div><div id="view" class="view hidden"></div><div id="search-results" class="search-results hidden"></div></main>
<script id="database" type="application/json"><!-- DATA --></script>
<script>
const DB=JSON.parse(document.getElementById('database').textContent);
const viewEl=document.getElementById('view'),directoryEl=document.getElementById('directory'),searchEl=document.getElementById('search'),resultsEl=document.getElementById('search-results'),crumbEl=document.getElementById('breadcrumbs');
let currentPath=[],previousPath=[],searchActive=false;
const typeNames={program:'Program',institution:'Institution',department:'Department',course:'Course'};
function theme(){return document.documentElement.dataset.theme||'light'}
function setTheme(value){document.documentElement.dataset.theme=value;localStorage.setItem('gameedudb-theme',value);document.getElementById('theme-toggle').textContent=value==='dark'?'Light mode':'Dark mode'}
setTheme(localStorage.getItem('gameedudb-theme')==='dark'?'dark':'light');
document.getElementById('theme-toggle').addEventListener('click',()=>setTheme(theme()==='dark'?'light':'dark'));
function renderBreadcrumbs(path){crumbEl.innerHTML='';if(!path.length)return;const root=document.createElement('a');root.href='#';root.textContent='Program Directory';crumbEl.append(root);path.forEach((part,index)=>{const sep=document.createElement('span');sep.textContent='›';crumbEl.append(sep);const item=DB.entities[part];if(!item)return;const link=document.createElement(index===path.length-1?'span':'a');link.textContent=item.name;if(index===path.length-1)link.className='current';else link.href='#'+path.slice(0,index+1).join('/');crumbEl.append(link)})}
function showPath(path){searchActive=false;searchEl.value='';currentPath=path;const key=path[path.length-1]||'';const view=DB.views[key];directoryEl.classList.add('hidden');resultsEl.classList.add('hidden');if(!view){viewEl.classList.add('hidden');directoryEl.classList.remove('hidden');renderBreadcrumbs([]);return}viewEl.innerHTML=view.body;viewEl.classList.remove('hidden');renderBreadcrumbs(path);document.title=view.title+' · GameEduDB';wireView();}
function route(){const parts=decodeURIComponent(location.hash.slice(1)).split('/').filter(Boolean);if(!parts.length){currentPath=[];searchActive=false;directoryEl.classList.remove('hidden');viewEl.classList.add('hidden');resultsEl.classList.add('hidden');crumbEl.innerHTML='';document.title='GameEduDB';return}const path=[];for(let i=0;i+1<parts.length;i+=2){const key=parts[i]+'/'+parts[i+1];if(DB.views[key])path.push(key)}showPath(path)}
function wireView(){viewEl.addEventListener('click',event=>{const link=event.target.closest('a[href^="#"]');if(!link)return;const target=decodeURIComponent(link.getAttribute('href').slice(1));if(DB.views[target]){event.preventDefault();location.hash=currentPath.concat(target).join('/')}});viewEl.querySelectorAll('.filter').forEach(button=>button.addEventListener('click',()=>{viewEl.querySelectorAll('.filter').forEach(x=>x.classList.remove('active'));button.classList.add('active');const filter=button.dataset.filter;viewEl.querySelectorAll('.filterable').forEach(card=>card.classList.toggle('hidden',filter!=='all'&&!card.dataset.classifications.split(' ').includes(filter)))}))}
function tokens(value){return value.toLocaleLowerCase().trim().split(/\s+/).filter(Boolean)}
function search(){const query=tokens(searchEl.value);if(!query.length){if(searchActive){searchActive=false;resultsEl.classList.add('hidden');if(currentPath.length)showPath(currentPath);else{directoryEl.classList.remove('hidden');viewEl.classList.add('hidden');renderBreadcrumbs([])}}return}if(!searchActive){previousPath=currentPath.slice();searchActive=true}directoryEl.classList.add('hidden');viewEl.classList.add('hidden');resultsEl.classList.remove('hidden');renderBreadcrumbs([]);const groups=['program','institution','department','course'];let out='';for(const type of groups){const matches=Object.entries(DB.entities).filter(([key,item])=>item.type===type&&query.every(token=>[item.name,item.code,item.description,item.institution].some(value=>value.toLocaleLowerCase().includes(token)))).sort((a,b)=>a[1].name.localeCompare(b[1].name,undefined,{numeric:true,sensitivity:'base'})||a[1].id.localeCompare(b[1].id));if(!matches.length)continue;out+=`<section><h2>${typeNames[type]}s (${matches.length})</h2>`;for(const [key,item] of matches){out+=`<a class="entity-card" href="#${key}"><div class="card-title">${escapeHTML(type==='course'&&item.code?item.code+': '+item.name:item.name)}</div>${item.institution&&type!=='institution'?`<div class="card-subtitle">${escapeHTML(item.institution)}</div>`:''}${item.description?`<div class="card-description">${escapeHTML(item.description)}</div>`:''}</a>`}out+='</section>'}resultsEl.innerHTML=out||'<div class="empty-state"><h2>No results found</h2><p>Try another search term or check your spelling.</p><button class="theme-toggle" id="clear-search">Clear search</button></div>';const clear=document.getElementById('clear-search');if(clear)clear.addEventListener('click',()=>{searchEl.value='';search()})}
function escapeHTML(value){return String(value).replace(/[&<>"']/g,char=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char]))}
searchEl.addEventListener('input',search);window.addEventListener('hashchange',route);route();
</script></body></html>'''

# main logic
def main():
    # check GameEduDB path
    if len(argv) == 1:
        root_path = Path(argv[0]).resolve().parent.parent
    elif len(argv) == 2:
        root_path = Path(argv[1]).resolve()
    else:
        print(f"USAGE: {argv[0]} [GameEduDB_path]"); exit(1)
    courses_path = root_path / 'courses'
    departments_path = root_path / 'departments'
    institutions_path = root_path / 'institutions'
    programs_path = root_path / 'programs'
    # load data; validity checking is intentionally performed elsewhere
    data = {
        data_path.name: {
            entry_path.name: {
                meta_path.stem: [
                    line.strip() for line in open(meta_path, mode='rt', encoding='utf-8') if len(line.strip()) != 0
                ] for meta_path in entry_path.glob('*.txt')
            } for entry_path in data_path.glob('*') if entry_path.is_dir()
        } for data_path in [institutions_path, departments_path, courses_path, programs_path]
    }
    # build output
    out = build_website(data)
    print(out, end='' if out.endswith('\n') else '\n')

# run script
if __name__ == "__main__":
    main()
