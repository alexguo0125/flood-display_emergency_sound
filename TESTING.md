# Testing Process

## Testing Approach

We tested the critical aspect of the prototype using scenario-based test cases. This was appropriate because the main design risk is whether users can quickly understand the flood-risk level and know what action to take from the e-ink display. The test cases covered the main display states: low risk, medium risk, high risk, connection lost, low battery, multilingual access, upload-based warning detection, and offline checklist support.

Each test case used the prototype controls, sample uploaded warning text, or the backend `/api/flood-status` endpoint to trigger a specific condition. We then checked whether the display showed the correct risk level, message, action, visual emphasis, and support information.

The old spreadsheet-based test artifact has been removed. The project now documents its official source review in `data/official_sources.json`, and the backend source availability can be checked with `/api/source-health`.

## Supporting Analysis

The official-source registry and backend normalization logic support the technical feasibility of the prototype by documenting the logic behind LOW, MEDIUM, HIGH, and OFFLINE states. It includes the intended official inputs, source references, display phrases, and test cases. This makes the design traceable: each display state can be linked back to an official source, a user scenario, and a tested prototype outcome.

The prototype also uses multilingual warning text and offline checklist assets to support the commercial and social feasibility of the design. These features respond to the need for public emergency information to be clear, accessible, and usable even when connectivity or device power is limited.

## Results And Impact On Design

Testing showed that the display needs a clear separation between flood-risk states and device/system states. LOW, MEDIUM, and HIGH should communicate different levels of urgency, while connection loss should not look like a safe condition. This led to a separate connection-lost mode that shows last-known risk information instead of falsely reassuring users.

The test cases also reinforced the need for short, action-focused messages. The HIGH state prioritises immediate action, the MEDIUM state encourages preparation, and the LOW state keeps users aware without creating panic. Multilingual testing supported the decision to keep key warning and action text available in multiple languages, and the offline checklist assets support use when live data or internet access is unavailable.
