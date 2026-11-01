import os

ledger_path = r'd:\The hobby 2\DigitalRevenueHilaweMiniApp\src\views\LedgerView.jsx'

with open(ledger_path, 'r', encoding='utf-8') as f:
    content = f.read()

start_marker = '  return (\n    <div className="space-y-6 md:space-y-8 animate-fade-in pb-12">'
end_marker = '      {/* Execution Console & Trend Visualizer Grid */}'

start_idx = content.find(start_marker)
end_idx = content.find(end_marker)

if start_idx == -1 or end_idx == -1:
    print(f"Error: start={start_idx}, end={end_idx}")
    exit(1)

new_ui_block = '''  return (
    <div className="space-y-6 md:space-y-8 animate-fade-in pb-12">
      {/* Financial Distribution Header */}
      <div className="premium-card p-5 sm:p-6 bg-gradient-to-r from-slate-900/90 via-slate-900/60 to-slate-950/80 border-white/[0.08] flex flex-col md:flex-row md:items-center justify-between gap-5">
        <div>
          <div className="flex items-center gap-2.5 flex-wrap">
            <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-[11px] font-semibold bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-400"></span>
              Live Accounting Cycle
            </span>
            <span className="text-xs text-slate-400 font-mono">
              Tri-Stream Financial Distribution
            </span>
          </div>
          <h2 className="text-xl sm:text-2xl font-black text-white tracking-tight mt-2.5">
            Partner Revenue & Settlement Controller
          </h2>
          <p className="text-xs text-slate-400 mt-1.5 max-w-2xl leading-relaxed">
            Real-time partner allocations. All infrastructure, hosting, and operational expenses are deducted solely from <span className="text-emerald-400 font-medium">Digital Product Sales</span>. Transformation Club and Meal Plan revenues are 100% protected.
          </p>
        </div>

        <div className="flex items-center gap-3 shrink-0">
          <button
            onClick={handleDownloadPendingStatement}
            className="px-4 py-2.5 rounded-xl bg-white/[0.05] hover:bg-white/[0.09] border border-white/[0.1] text-xs font-semibold text-white flex items-center gap-2 transition-all cursor-pointer active:scale-95 shadow-sm"
          >
            <i className="fa-solid fa-file-pdf text-rose-400"></i>
            <span>Export Statement</span>
          </button>
          <button
            onClick={fetchLedger}
            disabled={loading}
            className="p-2.5 rounded-xl bg-white/[0.05] hover:bg-white/[0.09] border border-white/[0.1] text-xs text-slate-300 hover:text-white transition-all cursor-pointer"
            title="Refresh Ledger"
          >
            <i className={`fa-solid fa-rotate-right ${loading ? 'animate-spin text-cyan-400' : ''}`}></i>
          </button>
        </div>
      </div>

      {/* Top 4 Financial Overview Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 sm:gap-5">
        {/* Card 1: Gross Revenue */}
        <div className="premium-card p-6 border-white/[0.08] relative">
          <div className="flex items-center justify-between text-xs text-slate-400 font-medium">
            <span>Pending Gross Revenue</span>
            <span className="px-2 py-0.5 rounded text-[10px] font-medium bg-cyan-500/10 text-cyan-400 border border-cyan-500/20">
              Unsettled
            </span>
          </div>
          <h3 className="text-2xl sm:text-3xl font-black text-white tracking-tight mt-2 font-mono tabular-nums whitespace-nowrap">
            {totalPendingGross.toLocaleString()} <span className="text-sm font-sans font-normal text-slate-400">ETB</span>
          </h3>
          <p className="text-[11px] text-slate-400 mt-2.5 flex items-center gap-1.5 flex-wrap">
            <span className="text-emerald-400 font-medium whitespace-nowrap">{prodGross.toLocaleString()} ETB Prod</span>
            <span>•</span>
            <span className="text-purple-400 font-medium whitespace-nowrap">{clubGross.toLocaleString()} ETB Club</span>
            <span>•</span>
            <span className="text-amber-400 font-medium whitespace-nowrap">{mealGross.toLocaleString()} ETB Meals</span>
          </p>
        </div>

        {/* Card 2: Operating Burn */}
        <div className="premium-card p-6 border-rose-500/20 bg-gradient-to-br from-rose-500/[0.03] to-transparent">
          <div className="flex items-center justify-between text-xs text-rose-400 font-medium">
            <span>Operating Burn (Deductions)</span>
            <span className="text-[10px] font-medium text-rose-400 bg-rose-500/10 px-2 py-0.5 rounded border border-rose-500/20">
              Digital Sales Solely
            </span>
          </div>
          <h3 className="text-2xl sm:text-3xl font-black text-rose-400 tracking-tight mt-2 font-mono tabular-nums whitespace-nowrap">
            -{enteredDeduction.toLocaleString()} <span className="text-sm font-sans font-normal text-slate-400">ETB</span>
          </h3>
          <p className="text-[11px] text-slate-400 mt-2.5">
            Servers, database, and infrastructure absorbed 100% by Stream A
          </p>
        </div>

        {/* Card 3: Coach Hilawe Entitlement */}
        <div className="premium-card p-6 border-amber-500/20 bg-gradient-to-br from-amber-500/[0.03] to-transparent">
          <div className="flex items-center justify-between text-xs text-amber-400 font-medium">
            <span>Coach Hilawe Payout</span>
            <span className="px-2 py-0.5 rounded text-[10px] font-mono bg-amber-500/10 text-amber-400 border border-amber-500/20">
              {totalPendingGross > 0 ? Math.round((totalCoachShare / totalPendingGross) * 1000) / 10 : 66.7}% of Gross
            </span>
          </div>
          <h3 className="text-2xl sm:text-3xl font-black text-white tracking-tight mt-2 font-mono tabular-nums whitespace-nowrap">
            {totalCoachShare.toLocaleString()} <span className="text-sm font-sans font-normal text-slate-400">ETB</span>
          </h3>
          <p className="text-[11px] text-slate-400 mt-2.5">
            {liveProdCoach.toLocaleString()} (70% Prod) + {liveClubCoach.toLocaleString()} ({clubCoachRate * 100}% Club) + {liveMealCoach.toLocaleString()} ({mealCoachRate * 100}% Meals)
          </p>
        </div>

        {/* Card 4: Dagmawi Tech Entitlement */}
        <div className="premium-card p-6 border-cyan-500/20 bg-gradient-to-br from-cyan-500/[0.03] to-transparent">
          <div className="flex items-center justify-between text-xs text-cyan-400 font-medium">
            <span>Dagmawi Tech Payout</span>
            <span className="px-2 py-0.5 rounded text-[10px] font-mono bg-cyan-500/10 text-cyan-400 border border-cyan-500/20">
              {totalPendingGross > 0 ? Math.round((totalDagShare / totalPendingGross) * 1000) / 10 : 33.3}% of Gross
            </span>
          </div>
          <h3 className="text-2xl sm:text-3xl font-black text-white tracking-tight mt-2 font-mono tabular-nums whitespace-nowrap">
            {totalDagShare.toLocaleString()} <span className="text-sm font-sans font-normal text-slate-400">ETB</span>
          </h3>
          <p className="text-[11px] text-slate-400 mt-2.5">
            {liveProdDag.toLocaleString()} (30% Prod) + {liveClubDag.toLocaleString()} ({Math.round((1 - clubCoachRate) * 100)}% Club) + {liveMealDag.toLocaleString()} ({Math.round((1 - mealCoachRate) * 100)}% Meals)
          </p>
        </div>
      </div>

      {/* Tri-Stream Revenue & Partner Distribution */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-5 sm:gap-6">
        {/* Stream A: Digital Products */}
        <div className="premium-card p-6 sm:p-7 flex flex-col justify-between border-emerald-500/20 bg-gradient-to-br from-emerald-500/[0.03] via-slate-900/40 to-transparent">
          <div>
            <div className="flex items-start justify-between gap-3 mb-5">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-xl bg-emerald-500/15 border border-emerald-500/30 flex items-center justify-center text-emerald-400 shrink-0">
                  <i className="fa-solid fa-dumbbell text-base"></i>
                </div>
                <div>
                  <h4 className="text-base font-bold text-white tracking-tight">Stream A: Digital Products</h4>
                  <p className="text-xs text-slate-400">Workout programs, nutrition plans & digital guides</p>
                </div>
              </div>
              <span className="px-2.5 py-1 rounded-full text-[10px] font-bold bg-emerald-500/15 text-emerald-400 border border-emerald-500/30 whitespace-nowrap shrink-0">
                Fixed 70 / 30 Split
              </span>
            </div>

            {/* Financial Ledger Section */}
            <div className="rounded-2xl bg-black/30 border border-white/[0.06] p-4.5 mb-5 space-y-3">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-[11px] font-medium text-slate-400">Gross Sales</p>
                  <p className="text-[10px] text-slate-500">{pendingData.products_stream?.count || 45} completed orders</p>
                </div>
                <p className="text-lg font-bold text-white font-mono tabular-nums whitespace-nowrap">
                  {prodGross.toLocaleString()} <span className="text-xs font-normal text-slate-400">ETB</span>
                </p>
              </div>

              <div className="flex items-center justify-between pt-2.5 border-t border-white/[0.05]">
                <div>
                  <p className="text-[11px] font-medium text-rose-400 flex items-center gap-1.5">
                    <span className="w-1.5 h-1.5 rounded-full bg-rose-400"></span>
                    Operating Burn (100% Absorbed)
                  </p>
                  <p className="text-[10px] text-slate-500">Servers, database, USD FX & product costs</p>
                </div>
                <p className="text-sm font-bold text-rose-400 font-mono tabular-nums whitespace-nowrap">
                  -{liveProdDeduct.toLocaleString()} <span className="text-xs font-normal text-rose-400/80">ETB</span>
                </p>
              </div>

              <div className="flex items-center justify-between pt-2.5 border-t border-emerald-500/20 bg-emerald-500/[0.04] -mx-4.5 -mb-4.5 p-4 rounded-b-2xl">
                <div>
                  <p className="text-[11px] font-bold text-emerald-300 uppercase tracking-wider">Net Distributable</p>
                  <p className="text-[10px] text-emerald-400/70">Available for partner split</p>
                </div>
                <p className="text-xl font-black text-emerald-400 font-mono tabular-nums whitespace-nowrap">
                  {liveProdNet.toLocaleString()} <span className="text-xs font-normal text-emerald-300/80">ETB</span>
                </p>
              </div>
            </div>

            {/* Partner Split Breakdown */}
            <div className="space-y-2.5">
              <div className="flex items-center justify-between text-xs p-3 rounded-xl bg-white/[0.02] border border-white/[0.05]">
                <div className="flex items-center gap-2">
                  <span className="w-2 h-2 rounded-full bg-amber-400"></span>
                  <span className="text-slate-300 font-medium">Coach Hilawe Semma (70%)</span>
                </div>
                <span className="text-white font-mono font-bold tabular-nums whitespace-nowrap">{liveProdCoach.toLocaleString()} ETB</span>
              </div>
              <div className="flex items-center justify-between text-xs p-3 rounded-xl bg-white/[0.02] border border-white/[0.05]">
                <div className="flex items-center gap-2">
                  <span className="w-2 h-2 rounded-full bg-cyan-400"></span>
                  <span className="text-slate-300 font-medium">Dagmawi Tewodros (30%)</span>
                </div>
                <span className="text-cyan-400 font-mono font-bold tabular-nums whitespace-nowrap">{liveProdDag.toLocaleString()} ETB</span>
              </div>
            </div>
          </div>

          <div className="mt-5 pt-3.5 border-t border-white/[0.06] flex items-center justify-between text-[11px] text-slate-400">
            <span>Contract Terms: Fixed 70/30</span>
            <span className="text-emerald-400 font-medium">Standard Partnership Split</span>
          </div>
        </div>

        {/* Stream B: Transformation Club */}
        <div className="premium-card p-6 sm:p-7 flex flex-col justify-between border-purple-500/20 bg-gradient-to-br from-purple-500/[0.03] via-slate-900/40 to-transparent">
          <div>
            <div className="flex items-start justify-between gap-3 mb-5">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-xl bg-purple-500/15 border border-purple-500/30 flex items-center justify-center text-purple-400 shrink-0">
                  <i className="fa-solid fa-users text-base"></i>
                </div>
                <div>
                  <h4 className="text-base font-bold text-white tracking-tight">Stream B: Transformation Club</h4>
                  <p className="text-xs text-slate-400">Monthly community subscriptions & renewals</p>
                </div>
              </div>
              <span className="px-2.5 py-1 rounded-full text-[10px] font-bold bg-purple-500/15 text-purple-400 border border-purple-500/30 whitespace-nowrap shrink-0">
                {isClubMature ? 'Stage 2: 65 / 35' : 'Stage 1: 60 / 40 Split'}
              </span>
            </div>

            {/* Financial Ledger Section */}
            <div className="rounded-2xl bg-black/30 border border-white/[0.06] p-4.5 mb-5 space-y-3">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-[11px] font-medium text-slate-400">Gross Subscriptions</p>
                  <p className="text-[10px] text-slate-500">{pendingData.club_stream?.count || 4} active members</p>
                </div>
                <p className="text-lg font-bold text-white font-mono tabular-nums whitespace-nowrap">
                  {clubGross.toLocaleString()} <span className="text-xs font-normal text-slate-400">ETB</span>
                </p>
              </div>

              <div className="flex items-center justify-between pt-2.5 border-t border-white/[0.05]">
                <div>
                  <p className="text-[11px] font-medium text-slate-400">Operating Deductions</p>
                  <p className="text-[10px] text-emerald-400/90 font-medium">100% Protected (Zero Burn Rate)</p>
                </div>
                <p className="text-sm font-bold text-slate-400 font-mono tabular-nums whitespace-nowrap">
                  0.00 <span className="text-xs font-normal text-slate-500">ETB</span>
                </p>
              </div>

              <div className="flex items-center justify-between pt-2.5 border-t border-purple-500/20 bg-purple-500/[0.04] -mx-4.5 -mb-4.5 p-4 rounded-b-2xl">
                <div>
                  <p className="text-[11px] font-bold text-purple-300 uppercase tracking-wider">Net Distributable</p>
                  <p className="text-[10px] text-purple-400/70">Equal to Gross Revenue</p>
                </div>
                <p className="text-xl font-black text-purple-400 font-mono tabular-nums whitespace-nowrap">
                  {liveClubNet.toLocaleString()} <span className="text-xs font-normal text-purple-300/80">ETB</span>
                </p>
              </div>
            </div>

            {/* Partner Split Breakdown */}
            <div className="space-y-2.5">
              <div className="flex items-center justify-between text-xs p-3 rounded-xl bg-white/[0.02] border border-white/[0.05]">
                <div className="flex items-center gap-2">
                  <span className="w-2 h-2 rounded-full bg-amber-400"></span>
                  <span className="text-slate-300 font-medium">Coach Hilawe Semma ({clubCoachRate * 100}%)</span>
                </div>
                <span className="text-white font-mono font-bold tabular-nums whitespace-nowrap">{liveClubCoach.toLocaleString()} ETB</span>
              </div>
              <div className="flex items-center justify-between text-xs p-3 rounded-xl bg-white/[0.02] border border-white/[0.05]">
                <div className="flex items-center gap-2">
                  <span className="w-2 h-2 rounded-full bg-cyan-400"></span>
                  <span className="text-slate-300 font-medium">Dagmawi Tewodros ({Math.round((1 - clubCoachRate) * 100)}%)</span>
                </div>
                <span className="text-cyan-400 font-mono font-bold tabular-nums whitespace-nowrap">{liveClubDag.toLocaleString()} ETB</span>
              </div>
            </div>
          </div>

          {/* 50,000 ETB Transition Milestone Gauge */}
          <div className="mt-5 p-3.5 rounded-2xl bg-purple-950/20 border border-purple-500/20">
            <div className="flex items-center justify-between text-xs mb-1.5">
              <span className="text-purple-300 font-medium">50,000 ETB Milestone Target</span>
              <span className="text-white font-mono font-bold tabular-nums">{clubProgress}%</span>
            </div>
            <div className="w-full bg-white/[0.06] h-2 rounded-full overflow-hidden">
              <div
                className="h-full rounded-full bg-gradient-to-r from-purple-500 to-indigo-400 transition-all duration-500"
                style={{ width: `${Math.min(100, Math.max(3, clubProgress))}%` }}
              ></div>
            </div>
            <div className="flex items-center justify-between text-[10px] text-slate-400 mt-2 font-mono tabular-nums">
              <span>{clubCumul.toLocaleString()} ETB recorded</span>
              <span>Target: {clubTarget.toLocaleString()} ETB (Then 65/35)</span>
            </div>
          </div>
        </div>

        {/* Stream C: Meal Plan Automation System */}
        <div className="premium-card p-6 sm:p-7 flex flex-col justify-between border-amber-500/20 bg-gradient-to-br from-amber-500/[0.03] via-slate-900/40 to-transparent">
          <div>
            <div className="flex items-start justify-between gap-3 mb-5">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-xl bg-amber-500/15 border border-amber-500/30 flex items-center justify-center text-amber-400 shrink-0">
                  <i className="fa-solid fa-bowl-food text-base"></i>
                </div>
                <div>
                  <h4 className="text-base font-bold text-white tracking-tight">Stream C: Meal Plan System</h4>
                  <p className="text-xs text-slate-400">Personalized nutrition, fasting protocols & PDFs</p>
                </div>
              </div>
              <span className="px-2.5 py-1 rounded-full text-[10px] font-bold bg-amber-500/15 text-amber-400 border border-amber-500/30 whitespace-nowrap shrink-0">
                {isMealMature ? 'Stage 2: 35% Dag / 65% Coach' : 'Stage 1: 40% Dag / 60% Coach'}
              </span>
            </div>

            {/* Financial Ledger Section */}
            <div className="rounded-2xl bg-black/30 border border-white/[0.06] p-4.5 mb-5 space-y-3">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-[11px] font-medium text-slate-400">Gross Plans Delivered</p>
                  <p className="text-[10px] text-slate-500">{pendingData.meal_stream?.count || 3} custom plans</p>
                </div>
                <p className="text-lg font-bold text-white font-mono tabular-nums whitespace-nowrap">
                  {mealGross.toLocaleString()} <span className="text-xs font-normal text-slate-400">ETB</span>
                </p>
              </div>

              <div className="flex items-center justify-between pt-2.5 border-t border-white/[0.05]">
                <div>
                  <p className="text-[11px] font-medium text-slate-400">Operating Deductions</p>
                  <p className="text-[10px] text-emerald-400/90 font-medium">100% Protected (Zero Burn Rate)</p>
                </div>
                <p className="text-sm font-bold text-slate-400 font-mono tabular-nums whitespace-nowrap">
                  0.00 <span className="text-xs font-normal text-slate-500">ETB</span>
                </p>
              </div>

              <div className="flex items-center justify-between pt-2.5 border-t border-amber-500/20 bg-amber-500/[0.04] -mx-4.5 -mb-4.5 p-4 rounded-b-2xl">
                <div>
                  <p className="text-[11px] font-bold text-amber-300 uppercase tracking-wider">Net Distributable</p>
                  <p className="text-[10px] text-amber-400/70">Equal to Gross Revenue</p>
                </div>
                <p className="text-xl font-black text-amber-400 font-mono tabular-nums whitespace-nowrap">
                  {liveMealNet.toLocaleString()} <span className="text-xs font-normal text-amber-300/80">ETB</span>
                </p>
              </div>
            </div>

            {/* Partner Split Breakdown */}
            <div className="space-y-2.5">
              <div className="flex items-center justify-between text-xs p-3 rounded-xl bg-white/[0.02] border border-white/[0.05]">
                <div className="flex items-center gap-2">
                  <span className="w-2 h-2 rounded-full bg-amber-400"></span>
                  <span className="text-slate-300 font-medium">Coach Hilawe Semma ({mealCoachRate * 100}%)</span>
                </div>
                <span className="text-white font-mono font-bold tabular-nums whitespace-nowrap">{liveMealCoach.toLocaleString()} ETB</span>
              </div>
              <div className="flex items-center justify-between text-xs p-3 rounded-xl bg-white/[0.02] border border-white/[0.05]">
                <div className="flex items-center gap-2">
                  <span className="w-2 h-2 rounded-full bg-cyan-400"></span>
                  <span className="text-slate-300 font-medium">Dagmawi Tewodros ({Math.round((1 - mealCoachRate) * 100)}%)</span>
                </div>
                <span className="text-cyan-400 font-mono font-bold tabular-nums whitespace-nowrap">{liveMealDag.toLocaleString()} ETB</span>
              </div>
            </div>
          </div>

          {/* 100,000 ETB Transition Milestone Gauge */}
          <div className="mt-5 p-3.5 rounded-2xl bg-amber-950/20 border border-amber-500/20">
            <div className="flex items-center justify-between text-xs mb-1.5">
              <span className="text-amber-300 font-medium">100,000 ETB Milestone Target</span>
              <span className="text-white font-mono font-bold tabular-nums">{mealProgress}%</span>
            </div>
            <div className="w-full bg-white/[0.06] h-2 rounded-full overflow-hidden">
              <div
                className="h-full rounded-full bg-gradient-to-r from-amber-500 to-orange-400 transition-all duration-500"
                style={{ width: `${Math.min(100, Math.max(3, mealProgress))}%` }}
              ></div>
            </div>
            <div className="flex items-center justify-between text-[10px] text-slate-400 mt-2 font-mono tabular-nums">
              <span>{mealCumul.toLocaleString()} ETB recorded</span>
              <span>Target: {mealTarget.toLocaleString()} ETB (Then 35/65)</span>
            </div>
          </div>
        </div>
      </div>\n\n'''

# Also update the settlement console operational deductions label
old_console_label = '''                <div className="flex items-center justify-between mb-1.5">
                  <label className="block text-xs font-medium text-slate-400">
                    Operational Deductions (ETB)
                  </label>
                  <span className="text-[10px] text-cyan-400">Auto Pro-Rata Split</span>
                </div>'''

new_console_label = '''                <div className="flex items-center justify-between mb-1.5">
                  <label className="block text-xs font-medium text-slate-400">
                    Operational Deductions (ETB)
                  </label>
                  <span className="text-[10px] text-emerald-400 font-medium">100% Digital Products</span>
                </div>'''

old_console_caption = '''                <p className="text-[10px] text-slate-400 mt-1">
                  Deductions split proportionally: {liveProdDeduct.toLocaleString()} Br Products / {liveClubDeduct.toLocaleString()} Br Club / {liveMealDeduct.toLocaleString()} Br Meals
                </p>'''

new_console_caption = '''                <p className="text-[10px] text-slate-400 mt-1">
                  Deductions are subtracted exclusively from Digital Product Sales. Club and Meal Plan earnings are 100% protected.
                </p>'''

content = content[:start_idx] + new_ui_block + content[end_idx:]

if old_console_label in content:
    content = content.replace(old_console_label, new_console_label, 1)

if old_console_caption in content:
    content = content.replace(old_console_caption, new_console_caption, 1)

with open(ledger_path, 'w', encoding='utf-8') as f:
    f.write(content)

print('Updated LedgerView.jsx successfully')
