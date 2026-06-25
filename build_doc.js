const { Document, Packer, Paragraph, TextRun, AlignmentType, BorderStyle } = require('docx');
const fs = require('fs');

const data = JSON.parse(fs.readFileSync(process.env.HOME + '/revision/curriculum.json', 'utf8'));
const courses = data.curriculum;

const totalCourses = courses.length;
const totalUnits   = courses.reduce((s, c) => s + c.units.length, 0);
const totalTopics  = courses.reduce((s, c) => s + c.units.reduce((su, u) => su + u.topics.length, 0), 0);

const children = [];

function hrule(color, size) {
    return new Paragraph({
        spacing: { before: 80, after: 80 },
        border: { bottom: { style: BorderStyle.SINGLE, size: size || 6, color: color || "2E75B6", space: 1 } },
        children: []
    });
}

function spacer(before, after) {
    return new Paragraph({ spacing: { before: before || 100, after: after || 100 }, children: [] });
}

children.push(spacer(400, 100));
children.push(new Paragraph({
    alignment: AlignmentType.CENTER,
    spacing: { before: 0, after: 120 },
    children: [new TextRun({ text: "NURSING FQE REVISION", bold: true, size: 52, font: "Arial", color: "1F3864" })]
}));
children.push(new Paragraph({
    alignment: AlignmentType.CENTER,
    spacing: { before: 0, after: 120 },
    children: [new TextRun({ text: "COMPLETE CURRICULUM TOPIC LIST", bold: true, size: 36, font: "Arial", color: "2E75B6" })]
}));
children.push(hrule("2E75B6", 12));
children.push(spacer(120, 120));
children.push(new Paragraph({
    alignment: AlignmentType.CENTER,
    spacing: { before: 0, after: 60 },
    children: [
        new TextRun({ text: totalCourses + " Courses", bold: true, size: 26, font: "Arial", color: "1F3864" }),
        new TextRun({ text: "   •   ", size: 26, font: "Arial", color: "888888" }),
        new TextRun({ text: totalUnits + " Units", bold: true, size: 26, font: "Arial", color: "1F3864" }),
        new TextRun({ text: "   •   ", size: 26, font: "Arial", color: "888888" }),
        new TextRun({ text: totalTopics + " Topics", bold: true, size: 26, font: "Arial", color: "1F3864" }),
    ]
}));
children.push(new Paragraph({
    alignment: AlignmentType.CENTER,
    spacing: { before: 60, after: 60 },
    children: [new TextRun({ text: "Telegram Channel: @re_vise", size: 22, font: "Arial", color: "2E75B6", italics: true })]
}));
children.push(hrule("2E75B6", 12));
children.push(spacer(200, 200));

var globalNum = 1;
courses.forEach(function(course, ci) {
    children.push(new Paragraph({
        spacing: { before: ci === 0 ? 0 : 400, after: 100 },
        border: { bottom: { style: BorderStyle.SINGLE, size: 3, color: "2E75B6", space: 4 } },
        children: [
            new TextRun({ text: "📘  " + course.course_name.toUpperCase(), bold: true, size: 28, font: "Arial", color: "1F3864" }),
            new TextRun({ text: "   (" + course.course_id + ")", size: 22, font: "Arial", color: "888888" })
        ]
    }));

    course.units.forEach(function(unit) {
        children.push(new Paragraph({
            spacing: { before: 200, after: 80 },
            children: [new TextRun({ text: "Unit " + unit.unit_number + " — " + unit.unit_name, bold: true, size: 24, font: "Arial", color: "2E75B6" })]
        }));

        unit.topics.forEach(function(topic) {
            children.push(new Paragraph({
                spacing: { before: 40, after: 40 },
                indent: { left: 480 },
                children: [
                    new TextRun({ text: globalNum + ".", size: 20, font: "Arial", color: "888888" }),
                    new TextRun({ text: "  " + topic.title, size: 20, font: "Arial", color: "1A1A1A" })
                ]
            }));
            globalNum++;
        });
    });
});

children.push(spacer(300, 100));
children.push(hrule("2E75B6", 6));
children.push(new Paragraph({
    alignment: AlignmentType.CENTER,
    spacing: { before: 120, after: 60 },
    children: [new TextRun({ text: "AI-generated revision sessions delivered automatically via @re_vise on Telegram.", size: 18, font: "Arial", color: "888888", italics: true })]
}));
children.push(new Paragraph({
    alignment: AlignmentType.CENTER,
    spacing: { before: 0, after: 60 },
    children: [new TextRun({ text: "Every topic. Every day. Until the FQE. 💪", size: 20, font: "Arial", color: "2E75B6", bold: true })]
}));

var doc = new Document({
    styles: { default: { document: { run: { font: "Arial", size: 20 } } } },
    sections: [{
        properties: {
            page: {
                size: { width: 11906, height: 16838 },
                margin: { top: 1440, right: 1440, bottom: 1440, left: 1440 }
            }
        },
        children: children
    }]
});

var outPath = process.env.HOME + '/revision/FQE_Curriculum_Topics.docx';
Packer.toBuffer(doc).then(function(buf) {
    fs.writeFileSync(outPath, buf);
    console.log('Done — ' + (globalNum - 1) + ' topics written to ' + outPath);
});
