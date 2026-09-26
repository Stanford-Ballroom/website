---
title: "{{ .Name | replaceRE `^week([0-9]+)$` `Week $1` }}: This week at Stanford Ballroom"
subject: ""
date: {{ .Date }}
draft: true
type: emails
url: /{{ .File.Path | strings.TrimSuffix ".md" }}.html
quarter: "Quarter YYYY"
preheader: "Add one sentence summarizing this week's news."
signer: Ro
lessons:
  title: "Monday, MONTH DAY"
  location: "Confirm this week's room and address"
  tracks:
    - name: Standard
      teacher: "'Ikaika"
    - name: Latin
      teacher: "Stacey, T&T"
  rows:
    - time: "6:30 – 7:30 pm"
      classes: [Beginner, Intermediate]
    - time: "7:30 – 8:30 pm"
      classes: [Intermediate, Beginner]
    - time: "8:30 – 9 pm"
      note: "Practice time, rounds, and office hours."
---
Happy Week X!

- Add this week's announcements here.

{{< email-snippet "schedule-v1" >}}

{{< email-snippet "beginners-v1" >}}

{{< email-lessons >}}

{{< email-event title="Mentored practice" status="tbd" >}}
We'll share the room and time once confirmed. Check the schedule for updates.
{{< /email-event >}}

{{< email-signoff >}}
