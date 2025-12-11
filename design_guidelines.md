# AI Roadmap Generator - Design Guidelines

## Design Approach
**Selected Approach:** Design System - Material Design inspired
**Rationale:** Enterprise productivity tool requiring clarity, structured data presentation, and professional credibility. Focus on information hierarchy and usability over visual flair.

## Typography System
- **Primary Font:** Inter (Google Fonts)
- **Secondary Font:** JetBrains Mono (for any code/technical elements)
- **Hierarchy:**
  - Page Headers: text-4xl/text-5xl, font-bold
  - Section Headers: text-2xl/text-3xl, font-semibold
  - Subsections: text-xl, font-semibold
  - Body Text: text-base/text-lg
  - Labels/Meta: text-sm, font-medium
  - Small Text: text-xs

## Layout & Spacing System
**Spacing Units:** Tailwind units of 4, 6, 8, 12, 16, 24
- Container: max-w-4xl for forms, max-w-6xl for results
- Section padding: py-12 md:py-16
- Card padding: p-6 md:p-8
- Element spacing: gap-6, space-y-8

## Home Page Structure

### Hero Section (No Image)
- Clean, professional header with centered content
- Main headline emphasizing AI transformation value
- Subheadline explaining the tool's purpose
- Height: Natural content height, not forced viewport
- Background: Subtle gradient or solid treatment

### Form Section
Single-column centered form (max-w-2xl):
- Form groups with clear labels above inputs
- Organization Size: Custom-styled dropdown with icon
- Industry: Text input with placeholder guidance
- AI Maturity: Segmented button group (3 options, radio behavior)
- Goals: Checkbox grid (2 columns on desktop, 1 on mobile) with clear iconography
- Submit button: Large, prominent, full-width on mobile
- Form validation states with inline feedback

## Results Page Structure

### Header
- Breadcrumb/back navigation
- Organization summary card displaying submitted inputs
- Download/share options (secondary actions)

### Roadmap Display
Three-phase accordion or tabbed interface:
- **Phase Cards:** Each phase as a distinct card with:
  - Phase header with timeline badge
  - Initiative cards within each phase containing:
    - Title (text-lg font-semibold)
    - Description (text-base)
    - Priority badge (High/Medium/Low with visual distinction)
  - Spacing between initiatives: space-y-4

### Gantt Chart Section
- Full-width container with subtle border
- Section header: "Timeline Visualization"
- Mermaid chart render area with minimum height
- Responsive scaling for mobile devices
- Light background to distinguish from content

## Component Library

### Cards
- Border style: border with subtle shadow
- Rounded corners: rounded-lg
- Hover state: subtle shadow elevation increase

### Buttons
- Primary: Solid fill, rounded-lg, px-8 py-3
- Secondary: Outline style
- Text: Minimal styling for tertiary actions

### Form Inputs
- Height: h-12
- Border: 2px solid
- Rounded: rounded-md
- Focus ring with offset
- Label spacing: mb-2

### Badges/Tags
- Rounded-full for priority indicators
- px-3 py-1, text-sm font-medium
- High Priority: Visually prominent
- Medium/Low: Progressively subtle

### Icons
**Library:** Heroicons (via CDN)
- Form field icons: 20px (h-5 w-5)
- Navigation icons: 24px (h-6 w-6)
- Badge icons: 16px (h-4 w-4)

## Navigation
Simple header with:
- Logo/brand name (text-xl font-bold)
- Optional: "How it works" link
- Minimal, clean navigation bar

## Responsive Behavior
- **Mobile (base):** Single column, full-width elements, stacked checkboxes
- **Tablet (md:):** 2-column checkbox grid, larger spacing
- **Desktop (lg:):** Full layout as designed, max-width containers

## Key UX Patterns
- Progressive disclosure: Show form → generate → results flow
- Loading state during API call with progress indicator
- Success feedback after generation
- Clear visual separation between roadmap phases
- Scannable initiative cards with consistent structure
- Print-friendly results layout

## Images
**Hero Section:** No hero image - focus on clean, professional typography and form presentation
**Results Page:** No decorative images - data and chart visualization are the primary visual elements

This design prioritizes clarity, professional credibility, and efficient information delivery for enterprise users generating strategic roadmaps.