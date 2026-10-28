import { useId } from 'react'

// Category-level concept art. No candidate-specific geometry or dimensions are implied.
function gearOutline(teeth: number, radius: number): string {
  const points = Array.from({ length: teeth * 4 }, (_, index) => {
    const angle = index * Math.PI / (teeth * 2)
    const r = index % 4 === 1 || index % 4 === 2 ? radius : radius - 7
    return `${(Math.cos(angle) * r).toFixed(2)},${(Math.sin(angle) * r).toFixed(2)}`
  })
  return `M${points.join('L')}Z`
}

export function PartIllustration({ kind, name = '零件' }: { kind: string; name?: string }) {
  const id = useId()
  const paint = (key: string) => `url(#${id}-${key})`
  const bolt = (x: number, y: number, r = 3) => <g key={`${x}-${y}`}>
    <circle cx={x} cy={y + 1} r={r + 1.4} fill="#7e94a9" opacity=".4" stroke="none" />
    <circle cx={x} cy={y} r={r} fill={paint('face')} stroke="#7e96aa" strokeWidth=".7" />
    <path d={`M${x-r*.5} ${y}h${r}`} stroke="#637c92" strokeWidth=".8" />
  </g>
  const mountingHole = (x: number, y: number, r = 3.4) => <g key={`${x}-${y}`}>
    <circle cx={x} cy={y} r={r + 1.2} fill="#eff3f6" stroke="#9dabb7" strokeWidth=".7"/>
    <circle cx={x} cy={y + .4} r={r} fill={paint('bore')} stroke="none"/>
    <path d={`M${x-r*.7} ${y+r*.4}q${r*.7} ${r*.6} ${r*1.4} 0`} fill="none" stroke="#afc0cc" strokeWidth=".7"/>
  </g>
  const socket = (cx: number, cy: number, rx: number, ry: number) => <g>
    <ellipse cx={cx} cy={cy} rx={rx} ry={ry} fill={paint('face')} stroke="#819bae" />
    <ellipse cx={cx} cy={cy} rx={rx - 5} ry={ry - 5} fill="none" stroke="#fff" strokeOpacity=".8" strokeWidth="1.5" />
    <ellipse cx={cx} cy={cy + 1} rx={rx * .65} ry={ry * .65} fill={paint('bore')} stroke="#5d778e" />
    <path d={`M${cx-rx*.6} ${cy+ry*.24}Q${cx} ${cy+ry*.83} ${cx+rx*.6} ${cy+ry*.24}`} fill="none" stroke="#afc6d7" strokeWidth="1.6" />
  </g>
  const cylinder = (x: number, width: number, r: number) => <g>
    <path d={`M${x} ${110-r}h${width}a8 ${r} 0 0 1 0 ${r*2}h-${width}z`} fill={paint('shaft')} />
    <ellipse cx={x} cy="110" rx="7" ry={r} fill={paint('face')} />
    <path d={`M${x+1} ${112-r}h${width-3}`} fill="none" stroke="#fff" strokeOpacity=".8" />
  </g>
  const gear = (x: number, y: number, scale = 1) => <g transform={`translate(${x} ${y}) rotate(-19) scale(${scale} ${scale*.78})`}>
    <path d={gearOutline(28, 65)} transform="translate(10 18) rotate(4)" fill={paint('steelSide')} stroke="#536776"/>
    {Array.from({ length: 28 }, (_, i) => {
      const a = i * Math.PI / 14
      return <path key={i} d={`M${Math.cos(a)*64} ${Math.sin(a)*64}L${10+Math.cos(a+.07)*65} ${18+Math.sin(a+.07)*65}`} stroke={i%2?'#9caebc':'#566e80'} strokeWidth="2.5"/>
    })}
    <path d={gearOutline(28, 65)} fill={paint('steel')} stroke="#677f90" strokeWidth=".8"/>
    <circle r="52" fill="none" stroke="#d3dfe7" strokeWidth="1.2"/>
    <circle r="48" fill={paint('steelWeb')} stroke="#697f90"/>
    {[31,33,36,43,45].map(r=><circle key={r} r={r} fill="none" stroke="#c5d2dc" strokeWidth=".5" opacity=".4"/>)}
    <circle r="26" fill={paint('face')} stroke="#879cab"/>
    <circle r="19" fill={paint('bore')} stroke="#687f90"/>
    {Array.from({length:12},(_,i)=><path key={i} d="M-1.8-19v3h3.6v-3" fill="#b1c1ce" stroke="#758c9d" strokeWidth=".5" transform={`rotate(${i*30})`}/>)}
    <path d="M-13 9Q0 21 13 9" fill="none" stroke="#b7ccdc" strokeWidth="1.3"/>
  </g>

  return <svg className="part-illustration" viewBox="0 0 360 220" role="img" aria-label={`${name}工程示意图`}>
    <defs>
      <linearGradient id={`${id}-backdrop`} x2=".8" y2="1"><stop stopColor="#fbfdff"/><stop offset="1" stopColor="#eaf1f8"/></linearGradient>
      <radialGradient id={`${id}-glow`} cx=".45" cy=".35" r=".65"><stop stopColor="#fff"/><stop offset="1" stopColor="#fff" stopOpacity="0"/></radialGradient>
      <linearGradient id={`${id}-metal`} x1=".15" y1="0" x2=".7" y2="1"><stop stopColor="#f0f5f9"/><stop offset=".28" stopColor="#c9d7e3"/><stop offset=".6" stopColor="#a4b9cb"/><stop offset="1" stopColor="#7c98af"/></linearGradient>
      <linearGradient id={`${id}-face`} x2=".8" y2="1"><stop stopColor="#fff"/><stop offset=".4" stopColor="#e2ebf2"/><stop offset=".76" stopColor="#b7cad9"/><stop offset="1" stopColor="#d7e3ec"/></linearGradient>
      <linearGradient id={`${id}-side`} x1="0" y1="0" x2=".8" y2="1"><stop stopColor="#afc3d3"/><stop offset=".5" stopColor="#809eb5"/><stop offset="1" stopColor="#53728c"/></linearGradient>
      <linearGradient id={`${id}-steel`} x1=".2" y1="0" x2=".85" y2="1"><stop stopColor="#c8d3dc"/><stop offset=".28" stopColor="#edf2f6"/><stop offset=".58" stopColor="#8ca2b4"/><stop offset="1" stopColor="#516a7d"/></linearGradient>
      <linearGradient id={`${id}-steelSide`} x2=".8" y2="1"><stop stopColor="#91a4b3"/><stop offset=".45" stopColor="#536b7e"/><stop offset="1" stopColor="#314c61"/></linearGradient>
      <linearGradient id={`${id}-steelWeb`} x1="0" y1=".1" x2="1" y2=".85"><stop stopColor="#6f879a"/><stop offset=".38" stopColor="#b3c1cd"/><stop offset=".8" stopColor="#617b8e"/><stop offset="1" stopColor="#839bac"/></linearGradient>
      <linearGradient id={`${id}-cast`} x1=".15" y1="0" x2=".8" y2="1"><stop stopColor="#d6dce0"/><stop offset=".4" stopColor="#b6c2cb"/><stop offset="1" stopColor="#8b9fab"/></linearGradient>
      <filter id={`${id}-grain`} x="0" y="0" width="1" height="1"><feTurbulence type="fractalNoise" baseFrequency=".75" numOctaves="2" seed="8" result="noise"/><feColorMatrix in="noise" type="saturate" values="0"/><feComponentTransfer><feFuncA type="linear" slope=".1"/></feComponentTransfer><feComposite in2="SourceGraphic" operator="in" result="grain"/><feBlend in="SourceGraphic" in2="grain" mode="multiply"/></filter>
      <linearGradient id={`${id}-shaft`} x1="0" y1="0" x2="0" y2="1"><stop stopColor="#8ca5ba"/><stop offset=".18" stopColor="#e6eef5"/><stop offset=".35" stopColor="#fbfdff"/><stop offset=".52" stopColor="#bdcddb"/><stop offset=".84" stopColor="#748fa7"/><stop offset="1" stopColor="#a1b8ca"/></linearGradient>
      <radialGradient id={`${id}-bore`} cx=".65" cy=".8" r=".85"><stop stopColor="#7d9cb3"/><stop offset=".55" stopColor="#435f77"/><stop offset="1" stopColor="#263f55"/></radialGradient>
      <filter id={`${id}-shadow`} x="-.4" y="-1" width="1.8" height="3"><feGaussianBlur stdDeviation="6"/></filter>
      <filter id={`${id}-object`} x="-.2" y="-.2" width="1.4" height="1.6"><feDropShadow dx="0" dy="5" stdDeviation="3" floodColor="#537791" floodOpacity=".16"/></filter>
    </defs>
    <rect width="360" height="220" rx="16" fill={paint('backdrop')} />
    <ellipse cx="180" cy="95" rx="160" ry="105" fill={paint('glow')} />
    <path d="M36 180H324" stroke="#dce7ef" strokeWidth=".8"/>
    <ellipse cx="183" cy="179" rx="98" ry="9" fill="#65849e" opacity=".2" filter={paint('shadow')} />
    <g stroke="#6e899e" strokeWidth="1" strokeLinejoin="round" filter={paint('object')}>
      {kind === 'shaft' ? <g transform="rotate(-12 180 110)">
        {cylinder(42, 62, 13)}{cylinder(103, 14, 22)}{cylinder(117, 100, 17)}{cylinder(217, 42, 34)}{cylinder(259, 38, 15)}{cylinder(297,18,9)}
        {[100,104,109,114,119].map(y=><path key={y} d={`M44 ${y}h57`} stroke="#577083" strokeWidth="1.5"/>)}
        {[102,107,112,117].map(y=><path key={y} d={`M45 ${y}h56`} stroke="#f3f7fa" strokeWidth=".7" opacity=".8"/>)}
        {[82,91,101,112,123,134].map(y=><path key={y} d={`M219 ${y}l37-8`} stroke="#516d82" strokeWidth="3"/>)}
        {[80,89,99,110,121,132].map(y=><path key={y} d={`M220 ${y}l35-8`} stroke="#d7e3ec" strokeWidth="1.3"/>)}
        <path d="M125 95h70m-68 2h61" stroke="#e4edf4" strokeWidth=".6"/>
        <path d="M113 89v42m96-35v29m54-28v26" stroke="#4a667b" strokeWidth="2"/>
        <ellipse cx="315" cy="110" rx="4" ry="9" fill={paint('face')}/>
      </g> : ['gear', 'gears'].includes(kind) ? <>
        {name.includes('组') || kind === 'gears' ? <>{gear(221, 82, .72)}{gear(137, 126, .93)}</> : gear(181, 110, 1.05)}
      </> : kind === 'flange' && !name.includes('取力器') ? <g transform="rotate(-9 180 110)">
        <path d="M162 68h71q22 2 22 41t-22 41h-71z" fill={paint('shaft')}/>
        <ellipse cx="233" cy="109" rx="15" ry="41" fill={paint('side')}/>
        <path d="M148 47h15a46 64 0 0 1 0 128h-15z" fill={paint('side')}/>
        <ellipse cx="148" cy="111" rx="50" ry="64" fill={paint('face')}/>
        <ellipse cx="148" cy="111" rx="44" ry="57" fill="none" stroke="#fff" strokeWidth="1.5"/>
        {Array.from({length:8},(_,i)=>mountingHole(148+Math.cos(i*Math.PI/4)*37,111+Math.sin(i*Math.PI/4)*47,3.8))}{socket(148,111,28,36)}
        {Array.from({length:12},(_,i)=><path key={i} d="M-2-22v4h4v-4" transform={`translate(148 112) scale(.7 1) rotate(${i*30})`} fill="#b2c3d0" strokeWidth=".6"/>)}
        <path d="M205 76v66m8-65v65" fill="none" stroke="#d8e6ef"/>
      </g> : kind === 'actuator' ? <>
        <path d="M85 96l32-25h113l26 23-29 28H85z" fill={paint('cast')} filter={paint('grain')}/>
        <path d="M227 122l29-28v57l-29 22z" fill={paint('side')}/>
        <path d="M85 96h142v77H85z" fill={paint('cast')} filter={paint('grain')}/>
        <rect x="105" y="112" width="80" height="43" rx="7" fill={paint('face')}/>
        <rect x="114" y="121" width="62" height="25" rx="4" fill="#e7eff6" stroke="#acbfce"/>
        <path d="M119 128h34m-34 7h46" stroke="#8aa7be" strokeWidth="1.6"/>
        <path d="M139 71V49l10-7h22v29" fill="#395b73"/>
        <path d="M139 49h22l10-7" fill="none" stroke="#e5eff7"/>
        <path d="M146 49v14m6-14v14m6-14v14" stroke="#93aebf" strokeWidth="1.4"/>
        <g transform="translate(-4 20)">{cylinder(260,39,13)}<ellipse cx="299" cy="110" rx="6" ry="13" fill={paint('side')}/></g>
        {[[95,106],[215,106],[95,163],[215,163]].map(([x,y])=>bolt(x,y))}
        <path d="M96 97h118" stroke="#fff" strokeOpacity=".85"/>
      </> : kind === 'pto' || name.includes('取力器') ? <>
        <path d="M137 59l83-12 46 24-86 17z" fill={paint('cast')} filter={paint('grain')}/>
        <path d="M180 88l86-17v76l-86 27z" fill={paint('side')} filter={paint('grain')}/>
        <path d="M91 71l21-16 73 12 20 21-1 77-21 18-72-14-20-21z" fill={paint('side')}/>
        <path d="M85 67l21-16 73 12 20 21-1 77-21 18-72-14-20-21z" fill={paint('face')}/>
        <path d="M95 73l15-11 65 11 13 15-1 68-15 12-61-12-16-17z" fill={paint('cast')} stroke="#8da5b6"/>
        {socket(142,113,30,37)}
        {[[107,72],[176,86],[106,112],[176,123],[107,151],[175,157]].map(([x,y])=>mountingHole(x,y,3.6))}
        <path d="M132 111h20v8h-20z" fill="#243e53" stroke="#b9cbd8"/>
        <path d="M218 93l31-6v44l-31 9z" fill={paint('cast')} stroke="#9aafbf"/>
        {bolt(224,99)}{bolt(243,95)}{bolt(224,130)}{bolt(243,125)}
      </> : name.includes('离合器') ? <>
        <path d="M147 49l97 26q33 32 0 73l-97 32z" fill={paint('cast')} filter={paint('grain')}/>
        <ellipse cx="243" cy="112" rx="23" ry="36" fill={paint('side')}/>
        {[73,91,130,149].map((y,i)=><g key={y}><path d={`M164 ${y}L240 ${89+i*15}`} stroke="#7e94a3" strokeWidth="5"/><path d={`M164 ${y-2}L240 ${87+i*15}`} stroke="#d1dce4" strokeWidth="1.4"/></g>)}
        <path d="M117 42v-7h34l8 11m-64 106-11 10 14 18 14-8m53-2 13 8 13-17-10-10" fill={paint('cast')}/>
        <ellipse cx="145" cy="113" rx="63" ry="73" fill={paint('side')}/>
        <ellipse cx="139" cy="111" rx="63" ry="73" fill={paint('face')}/>
        <ellipse cx="139" cy="111" rx="56" ry="65" fill="none" stroke="#fff" strokeWidth="2"/>
        <ellipse cx="139" cy="111" rx="47" ry="55" fill={paint('bore')}/>
        <ellipse cx="150" cy="117" rx="31" ry="39" fill="#8ea9bd" opacity=".65"/>
        <ellipse cx="158" cy="120" rx="19" ry="25" fill={paint('bore')}/>
        {Array.from({length:8},(_,i)=>mountingHole(139+Math.cos(i*Math.PI/4)*54,111+Math.sin(i*Math.PI/4)*63,3.2))}
        {mountingHole(132,40,3)}
      </> : <>
        <path d="M84 58l120-20 70 17-110 15z" fill={paint('cast')} filter={paint('grain')}/>
        <path d="M164 70l110-15 25 29-5 59-113 16 5-60z" fill={paint('cast')} filter={paint('grain')}/>
        <path d="M186 99l113-15-5 59-113 16z" fill={paint('side')} filter={paint('grain')}/>
        <path d="M71 85l25-22 69 13 25 26-5 62-27 26-76-15-24-29z" fill={paint('side')}/>
        <path d="M65 80l25-22 69 13 25 26-5 62-27 26-76-15-24-29z" fill={paint('face')}/>
        <path d="M76 86l19-17 58 11 19 22-5 51-20 19-63-12-19-24z" fill={paint('cast')} filter={paint('grain')}/>
        {socket(121,111,30,33)}
        {socket(85,139,14,16)}{socket(151,146,14,16)}
        {[[70,86],[99,66],[158,82],[174,107],[165,157],[147,178],[83,162],[62,137]].map(([x,y])=>mountingHole(x,y,2.8))}
        {[201,219,237,255,273].map(x=><g key={x}><path d={`M${x} ${97-(x-201)*.14}l-2 51 5 2 2-52z`} fill={paint('cast')} stroke="#748e9f"/><path d={`M${x} ${98-(x-201)*.14}l-2 49`} stroke="#d2dfe8" strokeWidth="1.2"/></g>)}
        <path d="M198 145l76-10v13l-76 12z" fill={paint('cast')} stroke="#8ba2b2"/>
        <path d="M260 104l21-3-1 28-21 4z" fill={paint('face')} stroke="#809aaa"/>
        {bolt(263,108,2)}{bolt(278,106,2)}{bolt(263,127,2)}{bolt(278,124,2)}
        <path d="M130 56l64-10 43 10-64 11z" fill={paint('face')} stroke="#91a7b7"/>
        {bolt(141,57,2)}{bolt(193,49,2)}{bolt(222,56,2)}{bolt(172,64,2)}
        <path d="M81 168v10l27 6v-11m123-24v12l26-4v-12" fill={paint('side')}/>
      </>}
    </g>
  </svg>
}
