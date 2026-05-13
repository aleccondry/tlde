.PHONY: run openrouter

run:
	uv run tlde "Emulate the nRF52833 micro:bit v2 using the specs in ./docs/nrf52833_rm.pdf and ./docs/microbit_v2_schematic.pdf"

openrouter:
	TLDE_PROVIDER=openrouter \
	TLDE_MODEL=z-ai/glm-5 \
	OPENROUTER_API_KEY=API_KEY \
	uv run tlde "Emulate the nRF52833 micro:bit v2 using the specs in ./docs/nrf52833_rm.pdf and ./docs/microbit_v2_schematic.pdf"
