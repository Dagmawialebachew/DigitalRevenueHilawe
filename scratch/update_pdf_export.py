import os

pdf_export_path = r'd:\The hobby 2\DigitalRevenueHilaweMiniApp\src\services\pdfExport.js'

with open(pdf_export_path, 'r', encoding='utf-8') as f:
    content = f.read()

# Replace the robotic header and text
old_header_text = """  doc.setFontSize(18);
  doc.text('DIGITAL FITNESS PARTNERSHIP', 16, 20);

  doc.setFontSize(11);
  doc.setFont('helvetica', 'normal');
  doc.setTextColor(148, 163, 184);
  doc.text('OFFICIAL SETTLEMENT & PROFIT DISTRIBUTION STATEMENT', 16, 28);

  doc.setFontSize(8);
  doc.setFont('courier', 'normal');
  doc.setTextColor(6, 182, 212);
  doc.text(`STATEMENT REF: ${refId}`, 16, 38);
  doc.text(`EFFECTIVE AGREEMENT: AUGUST 10, 2026 (ACTIVE TO MARCH 2, 2029)`, 16, 43);

  // Partner Identification Card
  doc.setFillColor(248, 250, 252);
  doc.roundedRect(15, 56, 180, 24, 2, 2, 'F');
  doc.setTextColor(15, 23, 42);
  doc.setFont('helvetica', 'bold');
  doc.setFontSize(9);
  doc.text('CONTRACTUAL PARTNERS:', 20, 63);

  doc.setFont('helvetica', 'normal');
  doc.setFontSize(8.5);
  doc.text('• Digital Systems Partner: Dagmawi Tewodros (Automation, Infrastructure, Delivery)', 20, 70);
  doc.text('• Content & Brand Partner: Coach Hilawe Semma (Fitness Content, Brand Identity)', 20, 75);"""

new_header_text = """  doc.setFontSize(17);
  doc.text('PARTNER REVENUE SETTLEMENT', 16, 20);

  doc.setFontSize(10.5);
  doc.setFont('helvetica', 'normal');
  doc.setTextColor(148, 163, 184);
  doc.text('OFFICIAL DISTRIBUTION STATEMENT & LEDGER SUMMARY', 16, 28);

  doc.setFontSize(8.5);
  doc.setFont('helvetica', 'bold');
  doc.setTextColor(6, 182, 212);
  doc.text(`STATEMENT ID: ${refId}`, 16, 38);
  doc.setFont('helvetica', 'normal');
  doc.setTextColor(148, 163, 184);
  doc.text(`ACCOUNTING CYCLE: Tri-Stream Partner Settlement`, 16, 43);

  // Partner Identification Card
  doc.setFillColor(248, 250, 252);
  doc.roundedRect(15, 56, 180, 24, 2, 2, 'F');
  doc.setTextColor(15, 23, 42);
  doc.setFont('helvetica', 'bold');
  doc.setFontSize(9);
  doc.text('PARTNERSHIP DISTRIBUTION:', 20, 63);

  doc.setFont('helvetica', 'normal');
  doc.setFontSize(8.5);
  doc.text('• Systems & Engineering Partner: Dagmawi Tewodros', 20, 70);
  doc.text('• Fitness & Brand Partner: Coach Hilawe Semma', 20, 75);"""

assert old_header_text in content, "old_header_text not found in pdfExport.js"
content = content.replace(old_header_text, new_header_text, 1)

# Replace table body logic
old_table_body = """  const tableBody = isExpense
    ? [
        ['Settlement Type', 'OPERATIONAL EXPENSE DEDUCTION (Section 5)'],
        ['Recorded Date', payoutDate],
        ['Expense Category', log.production_deductions > 0 ? 'Product & Video Production (Section 5.2)' : 'Technical Infrastructure & Server Hosting (Section 5.1)'],
        ['Deduction Amount', `-${deductions.toLocaleString('en-US', { minimumFractionDigits: 2 })} ETB`],
        ['Memo / Description', log.expense_note || 'General operating expense'],
      ]
    : [
        ['Settlement Execution Date', payoutDate],
        ['Stream A: Digital Products (Gross)', `${(prodGross || (grossTotal > 0 && !clubGross && !mealGross ? grossTotal : 0)).toLocaleString('en-US', { minimumFractionDigits: 2 })} ETB (Split: 70% Coach / 30% Dagmawi)`],
        ['Stream B: Transformation Club (Gross)', `${clubGross.toLocaleString('en-US', { minimumFractionDigits: 2 })} ETB (${log.club_stage === 'mature_65_35' ? 'Stage 2: 65% Coach / 35% Dagmawi' : 'Stage 1: 60% Coach / 40% Dagmawi Split'})`],
        ['Stream C: Meal Plan Automation (Gross)', `${mealGross.toLocaleString('en-US', { minimumFractionDigits: 2 })} ETB (${isMealMature ? 'Stage 2: 65% Coach / 35% Dagmawi' : 'Stage 1: 60% Coach / 40% Dagmawi Split (Until 100k ETB)'})`],
        ['Total Gross Revenue Pool', `${grossTotal.toLocaleString('en-US', { minimumFractionDigits: 2 })} ETB`],
        ['Allowable Operational Deductions', `-${deductions.toLocaleString('en-US', { minimumFractionDigits: 2 })} ETB`],
        ['Net Distributable Revenue', `${netProfit.toLocaleString('en-US', { minimumFractionDigits: 2 })} ETB`],
        ['Coach Hilawe Semma Entitlement', `${coachShare.toLocaleString('en-US', { minimumFractionDigits: 2 })} ETB`],
        ['Dagmawi Tewodros Entitlement', `${dagmawiShare.toLocaleString('en-US', { minimumFractionDigits: 2 })} ETB`],
      ];"""

new_table_body = """  const effectiveProdGross = (prodGross || (grossTotal > 0 && !clubGross && !mealGross ? grossTotal : 0));
  const prodNet = Math.max(0, effectiveProdGross - deductions);

  const tableBody = isExpense
    ? [
        ['Settlement Type', 'OPERATING EXPENSE RECORD'],
        ['Recorded Date', payoutDate],
        ['Expense Category', log.production_deductions > 0 ? 'Product & Video Production' : 'Servers, Database & Infrastructure'],
        ['Deduction Amount', `-${deductions.toLocaleString('en-US', { minimumFractionDigits: 2 })} ETB`],
        ['Allocation', 'Deducted 100% from Digital Product Sales (Stream A)'],
        ['Memo / Description', log.expense_note || 'Platform operating expense'],
      ]
    : [
        ['Settlement Date', payoutDate],
        ['Stream A: Digital Products (Gross)', `${effectiveProdGross.toLocaleString('en-US', { minimumFractionDigits: 2 })} ETB`],
        ['Stream A: Operating Deductions', deductions > 0 ? `-${deductions.toLocaleString('en-US', { minimumFractionDigits: 2 })} ETB (100% allocated to Stream A)` : '0.00 ETB'],
        ['Stream A: Net Distributable', `${prodNet.toLocaleString('en-US', { minimumFractionDigits: 2 })} ETB (Split: 70% Coach / 30% Tech)`],
        ['Stream B: Transformation Club (Gross)', `${clubGross.toLocaleString('en-US', { minimumFractionDigits: 2 })} ETB (Zero Burn - 100% Protected, ${log.club_stage === 'mature_65_35' ? '65/35' : '60/40'})`],
        ['Stream C: Meal Plan Automation (Gross)', `${mealGross.toLocaleString('en-US', { minimumFractionDigits: 2 })} ETB (Zero Burn - 100% Protected, ${isMealMature ? '65/35' : '60/40'})`],
        ['Total Gross Revenue Pool', `${grossTotal.toLocaleString('en-US', { minimumFractionDigits: 2 })} ETB`],
        ['Total Operating Deductions', `-${deductions.toLocaleString('en-US', { minimumFractionDigits: 2 })} ETB`],
        ['Net Distributable Revenue', `${netProfit.toLocaleString('en-US', { minimumFractionDigits: 2 })} ETB`],
        ['Coach Hilawe Semma Entitlement', `${coachShare.toLocaleString('en-US', { minimumFractionDigits: 2 })} ETB`],
        ['Dagmawi Tewodros Entitlement', `${dagmawiShare.toLocaleString('en-US', { minimumFractionDigits: 2 })} ETB`],
      ];"""

assert old_table_body in content, "old_table_body not found in pdfExport.js"
content = content.replace(old_table_body, new_table_body, 1)

# Replace the legal robotic confirmation text
old_footer = """  doc.text('SECTION 8 RECONCILIATION & EXECUTION CONFIRMATION', 15, currentY);

  doc.setFont('helvetica', 'normal');
  doc.setFontSize(7.5);
  doc.setTextColor(100, 116, 139);
  doc.text(
    'This statement certifies the exact profit distribution calculated in accordance with Sections 5, 6, and 8 of the Revised Digital Fitness Partnership Agreement. All figures are audited directly against verifiable bot payment ledgers and subscriber database records.',
    15,
    currentY + 6,
    { maxWidth: 180 }
  );"""

new_footer = """  doc.text('AUDIT CONFIRMATION & SETTLEMENT RECONCILIATION', 15, currentY);

  doc.setFont('helvetica', 'normal');
  doc.setFontSize(7.5);
  doc.setTextColor(100, 116, 139);
  doc.text(
    'This statement certifies the exact profit distribution across all three active revenue streams. Operational expenses are deducted strictly from Digital Product Sales; Transformation Club and Meal Plan earnings are 100% protected with zero burn rate.',
    15,
    currentY + 6,
    { maxWidth: 180 }
  );"""

assert old_footer in content, "old_footer not found in pdfExport.js"
content = content.replace(old_footer, new_footer, 1)

with open(pdf_export_path, 'w', encoding='utf-8') as f:
    f.write(content)

print('Updated pdfExport.js successfully')
