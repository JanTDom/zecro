# Adobe InDesign ExtendScript & IDML Reference

## Text Frame Threading Across Columns
```javascript
// Link two text frames for story flow
frame1.nextTextFrame = frame2;
frame2.nextTextFrame = frame3;
```

## Setting Up Baseline Grid Snapping
```javascript
var bodyStyle = doc.paragraphStyles.add({name: "Body Justified"});
bodyStyle.pointSize = 10;
bodyStyle.leading = 13.5;
bodyStyle.justification = Justification.LEFT_JUSTIFIED;
bodyStyle.alignToBaseline = true;
bodyStyle.hyphenation = true;
```
