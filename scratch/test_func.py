import ast

code = '''
def build_checkin_worksheet_html(plan, context, c, is_client, page_num, total_pages):
    scale_boxes = ""
    is_am = True
    w_lbl = "ክብደት፦"
    kg_lbl = "ኪ.ግ"
    waist_lbl = "የወገብ ስፋት፦"
    cm_lbl = "ሳ.ሜ"
    energy_lbl = "የሃይል መጠን (1-10)፦"
    hyd_lbl = "የውሃ አወሳሰድ (1-10)፦"
    notes_lbl = "የሳምንቱ ማስታወሻ፦"
    m_color = "#0284C7"
    m_badge_bg = "#E0F2FE"
    m_badge_fg = "#0369A1"
    m_badge = "ምዕራፍ 1"
    m_title = "Title"

    s = f"""
          <div class="worksheet-card" style="border-left: 4px solid {m_color};">
            <div class="worksheet-card-header">
              <span class="worksheet-card-title">{m_title}</span>
              <span class="worksheet-card-badge" style="background: {m_badge_bg}; color: {m_badge_fg};">{m_badge}</span>
            </div>
            <div class="worksheet-field">⚖️ <strong>{w_lbl}</strong> <span class="worksheet-line"></span> {kg_lbl}</div>
            <div class="worksheet-field">📏 <strong>{waist_lbl}</strong> <span class="worksheet-line"></span> {cm_lbl}</div>
            <div class="worksheet-field">
              ⚡️ <strong>{energy_lbl}</strong>
              <div class="worksheet-scale">{scale_boxes}</div>
            </div>
            <div class="worksheet-field">
              💧 <strong>{hyd_lbl}</strong>
              <div class="worksheet-scale">{scale_boxes}</div>
            </div>
            <div class="worksheet-field" style="margin-top: 1.5mm;">
              📝 <strong>{notes_lbl}</strong>
              <div style="border-bottom: 1.5px dotted #94A3B8; margin-top: 3.5mm;"></div>
            </div>
          </div>
    """
'''

try:
    ast.parse(code)
    print("Parsed standalone fine!")
except Exception as e:
    import traceback
    traceback.print_exc()
