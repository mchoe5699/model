package com.qwerty.model.registry;

import com.qwerty.model.QwertysModel;
import net.minecraft.core.registries.Registries;
import net.minecraft.network.chat.Component;
import net.minecraft.world.item.CreativeModeTab;
import net.minecraft.world.item.ItemStack;
import net.minecraftforge.registries.DeferredRegister;
import net.minecraftforge.registries.RegistryObject;

public final class ModTabs {
    public static final DeferredRegister<CreativeModeTab> TABS =
            DeferredRegister.create(Registries.CREATIVE_MODE_TAB, QwertysModel.MODID);

    public static final RegistryObject<CreativeModeTab> MAIN = TABS.register("main",
            () -> CreativeModeTab.builder()
                    .title(Component.translatable("itemGroup.qwertys_model"))
                    .icon(() -> new ItemStack(ModItems.HT100_DOOR_CAMERA.get()))
                    .displayItems((params, output) -> {
                        output.accept(ModItems.HT100_DOOR_CAMERA.get());
                        output.accept(ModItems.HT100_DOOR_CAMERA_AGED.get());
                    })
                    .build());

    private ModTabs() {}
}
