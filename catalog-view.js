(function(){
  const cfg=window.ATLAS_CONFIG||{};
  const fields=cfg.csvFields||[];
  const text=value=>value===null||value===undefined?'':value===true?'true':value===false?'false':String(value);
  const csvCell=value=>{let s=text(value);if(/^[=+\-@\t\r]/.test(s))s="'"+s;return /[",\r\n]/.test(s)?'"'+s.replaceAll('"','""')+'"':s;};
  const csvText=records=>'\ufeff'+[fields.map(field=>csvCell(field[1])).join(','),...records.map(record=>fields.map(field=>csvCell(record[field[0]])).join(','))].join('\r\n')+'\r\n';
  const downloadCsv=(records,name='ibaraki-fukeiin.csv')=>{const blob=new Blob([csvText(records)],{type:'text/csv;charset=utf-8'});const url=URL.createObjectURL(blob);const a=document.createElement('a');a.href=url;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);};
  const params=values=>new URLSearchParams(Object.entries(values).filter(([,value])=>value&&value!=='all')).toString();
  window.AtlasData={csvText,downloadCsv,params};
})();
