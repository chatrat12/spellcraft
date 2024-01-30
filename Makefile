V=1
SOURCE_DIR=src
BUILD_DIR=build
include $(N64_INST)/include/n64.mk

all: spellcraft.z64
.PHONY: all

###
# images
###

PNG_RGBA16 := $(shell find assets/ -type f -name '*.RGBA16.png' | sort)

MKSPRITE_FLAGS ?=

SPRITES := $(PNG_RGBA16:assets/%.RGBA16.png=filesystem/%.sprite)

filesystem/%.sprite: assets/%.RGBA16.png
	@mkdir -p $(dir $@)
	@echo "    [SPRITE] $@"
	@$(N64_MKSPRITE) -f RGBA16 --compress -o "$(dir $@)" "$<"

###
# meshes
###

BLENDER_4 := /home/james/Blender/blender-4.0.2-linux-x64/blender

filesystem/%.mesh: assets/%.blend
	@mkdir -p $(dir $@)
	@mkdir -p $(dir $(@:filesystem/%.mesh=build/assets/%.mesh))
	$(BLENDER_4) $< --background --python tools/mesh-export/__init__.py -- $(@:filesystem/%.mesh=build/assets/%.mesh)
	mkasset -o $(dir $@) -w 256 $(@:filesystem/%.mesh=build/assets/%.mesh)

###
# source code
###

SOURCES := $(shell find src/ -type f -name '*.c' | sort)
SOURCE_OBJS := $(SOURCES:src/%.c=$(BUILD_DIR)/%.o)
OBJS := $(BUILD_DIR)/main.o $(SOURCE_OBJS)

$(BUILD_DIR)/spellcraft.dfs: $(SPRITES)
$(BUILD_DIR)/spellcraft.elf: $(OBJS)

spellcraft.z64: N64_ROM_TITLE="SpellCraft"
spellcraft.z64: $(BUILD_DIR)/spellcraft.dfs

clean:
	rm -f $(BUILD_DIR)/* filesystem/ *.z64
.PHONY: clean

-include $(wildcard $(BUILD_DIR)/*.d)