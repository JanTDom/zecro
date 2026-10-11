import React from 'react';
import { useProject } from '../../context/ProjectContext';
import { apiUrl } from '../../api/client';

type Slot = {slot_id: string; story_ref: string; rank: string; col_start: number; col_span: number; row_start: number; row_span: number; module_type: string};
type Plan = {status: string; columns: number; rows: number; warnings: string[]; slots: Slot[]};
export const PagePlanner: React.FC = () => {
  const { activeProject } = useProject();
  const [stories, setStories] = React.useState([{id:'story-1',headline:'',body:'',rank:'lead',importance:1},{id:'story-2',headline:'',body:'',rank:'second',importance:.7}]);
  const [plan, setPlan] = React.useState<Plan | null>(null);
  const [status, setStatus] = React.useState('Wprowadź materiały i oblicz plan.');
  const build = async () => {
    if (!activeProject) return;
    try {
      const response = await fetch(apiUrl(`/projects/${activeProject.id}/page-plan`), {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({stories,page_zone:'front_page'})});
      const data = await response.json(); if (!response.ok) throw new Error(data.detail?.reason || data.detail || `API ${response.status}`);
      setPlan(data); setStatus(data.status === 'valid' ? 'Plan obliczony. Sprawdź sloty przed generowaniem.' : `Plan wymaga poprawek: ${data.warnings.join('; ')}`);
    } catch (error) { setStatus(`Plan niedostępny: ${error instanceof Error ? error.message : String(error)}`); }
  };
  return <main className="p-6 max-w-7xl mx-auto space-y-5"><header><h1 className="text-2xl font-semibold">Makieta strony</h1><p className="text-sm text-ink-500">Ustal hierarchię tekstów i sprawdź siatkę przed generowaniem.</p></header><p role="status" className="text-sm border rounded p-3">{status}</p>
    <div className="grid md:grid-cols-2 gap-5"><section className="space-y-3"><h2 className="font-semibold">Materiały</h2>{stories.map((story,index)=><div key={story.id} className="border rounded-lg p-3 bg-white space-y-2"><input aria-label={`Tytuł ${index+1}`} className="border rounded p-2 w-full" placeholder="Tytuł" value={story.headline} onChange={e=>setStories(list=>list.map((s,i)=>i===index?{...s,headline:e.target.value}:s))}/><textarea aria-label={`Tekst ${index+1}`} className="border rounded p-2 w-full" placeholder="Tekst" value={story.body} onChange={e=>setStories(list=>list.map((s,i)=>i===index?{...s,body:e.target.value}:s))}/><select aria-label={`Ranga ${index+1}`} className="border rounded p-2" value={story.rank} onChange={e=>setStories(list=>list.map((s,i)=>i===index?{...s,rank:e.target.value}:s))}>{['lead','second','third','short','brief','teaser','box','column'].map(rank=><option key={rank}>{rank}</option>)}</select></div>)}<button className="border rounded px-3 py-2" onClick={()=>setStories(list=>[...list,{id:`story-${Date.now()}`,headline:'',body:'',rank:'brief',importance:.5}])}>Dodaj materiał</button> <button className="bg-editorial-crimson text-white rounded px-3 py-2" onClick={()=>void build()}>Oblicz plan</button></section>
    <section><h2 className="font-semibold mb-3">Siatka</h2>{plan ? <div className="relative border bg-white aspect-[7/10]" style={{display:'grid',gridTemplateColumns:`repeat(${plan.columns},1fr)`,gridTemplateRows:`repeat(${plan.rows},1fr)`}}>{plan.slots.map(slot=><div key={slot.slot_id} className="border border-editorial-crimson bg-blue-50 p-1 text-xs overflow-hidden" style={{gridColumn:`${slot.col_start+1} / span ${slot.col_span}`,gridRow:`${slot.row_start+1} / span ${slot.row_span}`}}><strong>{slot.rank}</strong><br/>{stories.find(s=>s.id===slot.story_ref)?.headline || slot.story_ref}</div>)}</div> : <p className="text-sm text-ink-500">Plan pojawi się po obliczeniu.</p>}</section></div></main>;
};
