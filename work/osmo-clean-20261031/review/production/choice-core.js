export function canonicalChoice(value){
  const aliases={'iphone-fast':'phone','iphone-full':'native','osmo-lite':'osmo'};
  value=aliases[value]||value;return ['phone','native','osmo'].includes(value)?value:null;
}

// Selecting a radio or arriving through a deep link is not download consent.
// Only open() may launch the viewer, once, after the explicit Open model press.
export function createChoiceGate({preselected=null,onLaunch=()=>{}}={}){
  let selected=canonicalChoice(preselected),launched=false;
  return {
    select(value){if(launched)return false;selected=canonicalChoice(value);return Boolean(selected);},
    open(){if(launched||!selected)return null;launched=true;onLaunch(selected);return selected;},
    state(){return {selected,launched};}
  };
}

export function createLoadLifecycle(){
  let id=0,controller=null;
  return {
    begin(){controller?.abort();controller=new AbortController();return {id:++id,controller};},
  // A timeout aborts the current request but must still show its failure.
  // Supersession/cancel invalidate the token separately from AbortSignal.
  current(token){return token===id;},
    cancel(){controller?.abort();id++;}
  };
}
