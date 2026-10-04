import csv, ast
from collections import defaultdict
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer, Image, Table, TableStyle,
                                PageBreak, Preformatted, KeepTogether)

# Team members shown on the cover page (edit here to add/remove people)
TEAM = [("Ekta", "B23CS1018"),
        ("Tavishi Srivastava", "B23CS1101"),
        ("Shreekar", "B23CS1069")]

ss = getSampleStyleSheet()
B = ParagraphStyle("B", parent=ss["BodyText"], fontSize=10, leading=14, spaceAfter=6)
H1 = ParagraphStyle("H1", parent=ss["Heading1"], keepWithNext=1, fontSize=15, spaceBefore=10, spaceAfter=6)
H2 = ParagraphStyle("H2", parent=ss["Heading2"], keepWithNext=1, fontSize=12, spaceBefore=8, spaceAfter=4)
CAP = ParagraphStyle("CAP", parent=B, fontSize=8.5, leading=11, textColor=colors.HexColor("#444444"))
CODE = ParagraphStyle("CODE", fontName="Courier", fontSize=8, leading=10, backColor=colors.HexColor("#f3f3f3"),
                      borderPadding=4, spaceAfter=8)
TC = ParagraphStyle("TC", parent=B, fontSize=8, leading=10, spaceAfter=0)

def P(t): return Paragraph(t, B)
def bullets(items): return [Paragraph("&bull; " + i, ParagraphStyle("bl", parent=B, leftIndent=14, firstLineIndent=-8, spaceAfter=3)) for i in items]
def tbl(data, widths, header=True, fs=8):
    d = [[Paragraph(str(c), TC) for c in r] for r in data]
    t = Table(d, colWidths=widths, repeatRows=1)
    st = [("GRID", (0, 0), (-1, -1), 0.4, colors.grey), ("VALIGN", (0, 0), (-1, -1), "TOP"),
          ("TOPPADDING", (0, 0), (-1, -1), 2), ("BOTTOMPADDING", (0, 0), (-1, -1), 2)]
    if header: st.append(("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#dde6f0")))
    t.setStyle(TableStyle(st)); return t
def fig(path, w, cap):
    from PIL import Image as PI
    iw, ih = PI.open(path).size
    return KeepTogether([Image(path, width=w, height=w * ih / iw), Paragraph(cap, CAP), Spacer(1, 6)])

# ---------- data ----------
rows = list(csv.DictReader(open("results/sweep.csv")))
g = defaultdict(list)
for r in rows: g[(r["mode"], int(r["n_agents"]), float(r["dyn_density"]))].append(r)
def m(xs): xs = list(xs); return sum(xs) / len(xs) if xs else float("nan")
def agg(mode, n, d):
    sub = g[(mode, n, d)]; ok = [r for r in sub if r["completed"] == "True"]
    return dict(ok=len(ok), tot=len(sub), t=m(float(r["sum_time"]) for r in ok),
                chg=m(float(r["avg_changed_impactful"]) for r in sub), mx=max(int(r["max_changed"]) for r in sub),
                delay=m(float(r["sum_time"]) - float(r["initial_sum"]) for r in ok),
                cpu=m(float(r["repair_cpu"]) for r in sub))
frows = list(csv.DictReader(open("results/failures.csv")))

story = []
story += [Paragraph("Decentralised Plan Repair for a Multi-Robot Warehouse under Dynamic Disruptions", ParagraphStyle("T", parent=ss["Title"], fontSize=18, leading=22)),
          Paragraph("Autonomous Assignment Report", ParagraphStyle("S", parent=B, alignment=1, fontSize=11)),
          Paragraph("Group members", ParagraphStyle("GM", parent=B, alignment=1, fontSize=11, spaceAfter=3)),
          tbl([["Name", "Roll No."]] + [[n, r] for n, r in TEAM], [6.5*cm, 4*cm]),
          Spacer(1, 8)]

story += [Paragraph("1. Problem statement", H1),
  P("A warehouse is modelled as a 2D grid with static shelves. Each robot starts at a cell and must visit, in order, a list of "
    "pickup and drop-off locations. Initial collision-free paths come from a multi-agent path-finding algorithm (Space-Time A*). "
    "During execution the environment changes: a cell can be blocked, a robot can break down, or a robot can receive an urgent task. "
    "The robots must repair their plans <b>without re-invoking the global planner</b>, and the repair should change the plans of as "
    "few robots as possible. We evaluate (i) the total time steps needed by all agents, (ii) the number of agents whose plan is "
    "changed per disruption, and (iii) how both vary with the number of agents and the density of dynamic obstacles. We also "
    "identify settings where the system fails."),
  Paragraph("2. System design", H1),
  P("The implementation is in Python and split into modules: <font face='Courier'>grid.py</font> (map and warehouse layout), "
    "<font face='Courier'>planner.py</font> (Space-Time A* and reservation table), <font face='Courier'>repair.py</font> (plan repair "
    "and negotiation), <font face='Courier'>sim.py</font> (time-step simulator, disruptions, metrics), "
    "<font face='Courier'>viz.py</font> (GIF animation), <font face='Courier'>viz_html.py</font> (interactive viewer) and <font face='Courier'>run_experiments.py</font>."),
  Paragraph("2.1 Environment", H2),
  P("The default map is 20x20 with shelf blocks (2x4 cells) separated by aisles of width 2; width 1 is used as a failure setting. "
    "Robots move one cell per step in 4 directions or wait. Each robot has 2 tasks (pickup next to a shelf, drop-off on the border), "
    "so 4 waypoints. A robot that finishes parks on its last cell and remains an obstacle for the others."),
  Paragraph("2.2 Space-Time A* with reservations", H2),
  P("A search state is (cell, time). Moves are the four directions plus wait. The heuristic is the true shortest-path distance on the "
    "static map (BFS), which is admissible. A move to (c, t+1) is rejected if the reservation table says that (i) another agent "
    "occupies c at t+1 (vertex conflict), (ii) another agent moves c to the current cell during the same step (swap/edge conflict), "
    "(iii) a robot is parked on c from a time not later than t+1, or (iv) a dynamic obstacle blocks c at t+1. "
    "For the last waypoint the agent parks, so the goal is only accepted after every other reservation on that cell has expired. "
    "Initial plans use prioritised planning: agent 0 plans first and reserves its path, agent 1 plans around it, and so on."),
  Paragraph("2.3 Disruptions", H2)]
story += bullets([
  "<b>Blocked cell:</b> a free, unoccupied cell becomes impassable for a random duration (5 to 15 steps). Agents whose plans use the cell during that interval are the <i>affected</i> agents.",
  "<b>Robot breakdown:</b> a robot freezes in its cell for N steps (or permanently). Its cell is reserved as occupied; agents whose plans pass through it are affected. After recovery the robot re-plans.",
  "<b>Emergency task:</b> an extra waypoint is inserted at the front of a robot's task list; the robot must re-plan to visit it first."])
story += [P("Dynamic obstacle <i>density</i> is defined as the expected fraction of free cells that is blocked at any moment. "
            "Block events are generated from this value (number of events = density x free cells x horizon / mean duration), "
            "and breakdowns and emergencies are added at fixed counts (2 each in the main sweep).")]

story += [Paragraph("3. Plan repair and negotiation", H1),
  P("When a disruption occurs, only the affected agents start a repair. A repair never calls the multi-agent planner; every agent "
    "keeps its current plan unless the repair explicitly changes it. Each disrupted agent climbs an <b>escalation ladder</b>:"),]
story += bullets([
  "<b>Level 1 - self repair:</b> remove the agent's own reservations and re-plan only that agent against everybody else's unchanged plans. If it succeeds, exactly one agent has changed.",
  "<b>Level 2 - negotiate with one neighbour:</b> agents within Manhattan distance <i>r</i> (default 8) are candidates. For each candidate the disrupted agent plans first, then the candidate <i>yields</i>, i.e. re-plans its remaining route around the new path. The option with the least extra delay is committed.",
  "<b>Level 3 - two neighbours</b> (pairs among the 5 nearest) and <b>level 4 - the k nearest neighbours</b> (k up to 3).",
  "<b>Failure - hold:</b> the agent stays in place (its cell is reserved) and retries every 4 steps. If it is still stuck after 30 steps it is declared failed."])
story += [P("A neighbour that is asked to yield can also be a robot that has already finished; it then has to leave and come back to its cell. "
            "If a forced hold overwrites someone else's reservation, that agent is detected as displaced and repaired in turn (cascade). "
            "In the report, the number of <i>agents changed</i> for one disruption is computed by comparing every agent's remaining path "
            "before and after the event (trailing waits ignored)."),
  Preformatted(
"""repair(disrupted agents A):
  for a in A (by id):
      if replan_alone(a):                 # level 1
          continue
      for k in 1..max_group:              # levels 2..4
          best = None
          for group G of k neighbours within radius r:
              plans = trial(a, G)         # a plans first, then each g in G re-plans
              if plans ok and cost(plans) < best.cost: best = (G, plans)
          if best: commit(best); break
      else:
          hold(a)                         # retry later; may displace others
      re-run repair for agents displaced by a hold (max 3 times each)""", CODE)]

story += [Paragraph("4. Experimental setup", H1),
  P("All experiments use a 20x20 warehouse with aisle width 2, 2 tasks per agent, 2 breakdowns (duration 6 to 20 steps) and 2 emergency tasks per run, "
    "and a maximum of 400 steps. <b>Experiment A</b> varies the number of agents (5, 10, 15, 20, 25) and obstacle density (0, 2, 4, 6, 8%) with 10 random seeds "
    "per cell, for our local repair and for a <b>baseline</b> that, on every disruption, discards all plans and re-plans every agent from scratch "
    "(used only for comparison). Both modes see identical events for the same seed. <b>Experiment B</b> deliberately stresses the system (10 seeds each). "
    "Metrics: <b>total time steps</b> = sum over agents of the step at which each finishes its last task (reported over successful runs); "
    "<b>agents changed per disruption</b> averaged over disruptions that affected at least one agent; <b>success</b> = all agents completed all tasks. "
    "A built-in collision check (vertex, swap, entering a blocked cell) reported 0 collisions in all runs reported here."),
  Paragraph("5. Visualisation", H1),
  P("<font face='Courier'>run_demo.py</font> produces two outputs from the same simulation run. "
    "<font face='Courier'>demo.gif</font> is an animation, and <font face='Courier'>demo.html</font> is an interactive viewer that opens in any web browser "
    "and supports pause, about 10 seconds backward/forward, single steps, a time slider and jumping to each disruption. "
    "The warehouse is drawn as a labelled 2D grid (x across, y down): shelves are dark grey, blocked cells are red with a white cross and their (x,y) coordinates, "
    "and a freshly blocked cell gets a gold outline. Every robot shows its ID inside its cell, and a side panel lists the cell of every robot at every step. "
    "Planned paths stay visible; a robot that was just re-planned gets an orange ring and its previous plan is drawn dashed, so the repair can be compared with the original plan. "
    "The screenshot below is from the scripted demo (8 robots)."),
  fig("results/frame_block.png", 15 * cm, "Figure 1: a cell, (1,9), is blocked at t=6 (red, gold outline). Only robot 0, whose path crossed it, re-plans (orange ring); its old plan is the dashed line."),
  ]
story += [Paragraph("6. Results", H1), Paragraph("6.1 Effect of the number of agents and obstacle density", H2),
  fig("results/sum_time.png", 15.5 * cm, "Figure 2: total time steps (sum over agents, successful runs). Solid = local repair, dashed = replan-everything baseline.")]
dens_list = [0.0, 0.04, 0.08]
data = [["Agents", "Density", "Success local", "Total steps local", "Total steps full", "Agents changed local", "Agents changed full", "Max changed local / full"]]
for n in (5, 10, 15, 20, 25):
    for d in dens_list:
        a, b = agg("local", n, d), agg("full", n, d)
        data.append([n, f"{d:.0%}", f"{a['ok']}/{a['tot']}", f"{a['t']:.0f}", f"{b['t']:.0f}", f"{a['chg']:.2f}", f"{b['chg']:.2f}", f"{a['mx']} / {b['mx']}"])
story += [tbl(data, [1.3*cm, 1.4*cm, 2.2*cm, 2.3*cm, 2.2*cm, 2.5*cm, 2.5*cm, 2.6*cm]),
          Paragraph("Table 1: selected results (full grid in results/sweep.csv). 'Agents changed' = mean over disruptions that affected at least one agent.", CAP), Spacer(1, 6),
  fig("results/avg_changed_impactful.png", 15.5 * cm, "Figure 3: agents whose plan changed per disruption."),
  fig("results/completed.png", 15.5 * cm, "Figure 4: success rate (fraction of runs in which every agent finished).")]
a05, a25 = agg("local", 5, 0.04), agg("local", 25, 0.04)
f05, f25 = agg("full", 5, 0.04), agg("full", 25, 0.04)
story += [Paragraph("Observations", H2)]
story += bullets([
  f"<b>Plan changes are small and do not grow with fleet size under local repair.</b> The local repair re-plans about {a05['chg']:.1f} agents per affected disruption with 5 agents and {a25['chg']:.1f} with 25 (4% density). The replan-everything baseline grows from {f05['chg']:.1f} to {f25['chg']:.1f}, roughly proportional to the fleet, with a maximum of up to 25 agents in a single disruption versus at most 7 for local repair in the whole sweep.",
  "<b>Total time steps are essentially the same for both strategies</b> (differences of a few percent, in either direction), so keeping most plans untouched costs no measurable efficiency in these experiments. The baseline does however spend more computation: its repair CPU time per run is larger, e.g. about 0.45 s versus 0.06 s at 20 agents and 8% density (sweep.csv, column repair_cpu).",
  "<b>Total time grows roughly linearly with the number of agents</b> (about 66 steps per added agent), because it is a sum over agents.",
  "<b>Obstacle density increases total time moderately.</b> Going from 0% to 8% adds roughly 30 to 140 extra steps in total for 5 to 25 agents (measured against the initial plan cost, the 'delay' column in sweep.csv). Part of the delay at 0% (about 40 to 45 steps) comes from the breakdowns and emergency tasks, which are present in every run.",
  "<b>Success rate stays high</b> (at least 8 of 10 in every cell) but drops occasionally for 10 to 25 agents at 4 to 8% density in both modes."])

story += [Paragraph("6.2 Failure analysis: settings where agents fail to complete their tasks", H2),
  P("We searched for breaking points by stressing one factor at a time (10 seeds per setting, 20x20 map unless stated, 2 breakdowns and 2 emergencies unless stated). "
    "'Stuck' means a robot could not find any plan, even with negotiation, for 30 consecutive steps. 'Initial plan' means prioritised planning found no path for that robot at time 0."),
  fig("results/failures.png", 14.5 * cm, "Figure 5: success counts for the stress settings.")]
data = [["Setting", "Completed", "Agents done (mean fraction)", "Agents changed", "Failure reasons (counts of agents over all runs)"]]
for r in frows:
    data.append([r["setting"], f"{r['completed']}/{r['runs']}", r["agents_done"], r["avg_changed"], r["reasons"].replace("'", "")])
story += [tbl(data, [5.2*cm, 1.8*cm, 2.3*cm, 1.8*cm, 5.6*cm]), Paragraph("Table 2: failure experiments (results/failures.csv).", CAP)]
story += [Paragraph("Why the failures happen", H2)]
story += bullets([
  "<b>Shared delivery stations (0/10).</b> With only 3 stations, the first robot that finishes parks on one, and every later robot that needs it can never deliver (121 agent-level initial-plan failures). This is the 'goal cell occupied' case: a parked robot is a permanent obstacle. A fix would be to let finished robots leave the grid or move to a waiting area.",
  "<b>Narrow 1-wide aisles (4/10).</b> Two robots meeting head-on in a single-width corridor cannot pass, and waiting does not help. Prioritised planning also fails at time 0 for some agents (5 initial-plan failures) because earlier robots park in or reserve the only route. Several robots then end up stuck.",
  "<b>Dense maps (12x12 with 20 agents: 8/10; 35 agents on 20x20: 8/10).</b> With many robots there is too little free space for a conflict-free path within the search horizon, and stuck robots hold their cell, which blocks others in turn. We did not diagnose each stuck robot individually, so we describe the cause as congestion consistent with these configurations rather than proven per case.",
  "<b>Permanent breakdowns (0/10, but 8/10 for the remaining robots).</b> By definition the broken robots never finish. The other robots mostly route around them, but in 2 cases a robot also became stuck (a dead robot can sit in a cell that others need).",
  "<b>High obstacle density (12%: 9/10), many emergencies (9/10).</b> Both stay mostly robust; the single failure in each case is again a stuck robot.",
  "<b>Small negotiation radius (r=0 or 2: 8/10 at 8% density).</b> Success and agents changed were the same as with the default radius in our runs, so we could not show a benefit of negotiation in this setting. Level 1 (self repair) resolves almost all disruptions here, so negotiation is rarely needed; it matters only in congested cases, where it also often fails."])

story += [Paragraph("7. Limitations and possible improvements", H1)]
story += bullets([
  "Prioritised planning is incomplete: it can fail for some priority orders. Retrying with other orders, or a complete method such as CBS, would remove some initial-plan failures.",
  "Finished robots stay parked, which is the main cause of the station-contention failures. Letting them leave the floor would help.",
  "Stuck robots do not coordinate beyond the distance-based neighbour ladder. Deadlock detection and explicit swapping or back-off protocols would help in narrow aisles.",
  "Neighbours are chosen by Manhattan distance only; choosing agents whose plans actually conflict could find better negotiation partners.",
  "Negotiation is simulated centrally (one process evaluates each neighbour's reply with the shared reservation table); a real deployment would exchange messages.",
  "Results are for one map size, 2 tasks per agent and 10 seeds per cell, so small differences should not be over-interpreted."])
story += [Paragraph("8. Conclusion", H1),
  P("A repair scheme that first re-plans only the disrupted agent and escalates to nearby neighbours only when needed kept the number of "
    "re-planned agents per disruption at about one to two regardless of fleet size, while matching the total time steps of replanning "
    "everything and using less computation. The system failed in clearly identifiable conditions: contested delivery cells, "
    "single-width aisles, very crowded maps and permanent breakdowns."),
  Paragraph("Appendix: how to reproduce", H1),
  P("<font face='Courier'>python run_demo.py</font> produces demo.gif. <font face='Courier'>python run_experiments.py</font> reproduces sweep.csv, failures.csv and the plots. "
    "Seeds are fixed, so runs are reproducible.")]

doc = SimpleDocTemplate("report.pdf", pagesize=A4, leftMargin=2*cm, rightMargin=2*cm, topMargin=1.8*cm, bottomMargin=1.8*cm,
                        title="Plan repair for multi-robot warehouse")
doc.build(story)
print("ok")
