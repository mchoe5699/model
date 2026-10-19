package com.qwerty.model;

import com.qwerty.model.registry.ModBlocks;
import com.qwerty.model.registry.ModItems;
import com.qwerty.model.registry.ModTabs;
import net.minecraftforge.eventbus.api.IEventBus;
import net.minecraftforge.fml.common.Mod;
import net.minecraftforge.fml.javafmlmod.FMLJavaModLoadingContext;

@Mod(QwertysModel.MODID)
public class QwertysModel {
    public static final String MODID = "qwertys_model";

    public QwertysModel() {
        IEventBus bus = FMLJavaModLoadingContext.get().getModEventBus();
        ModBlocks.BLOCKS.register(bus);
        ModItems.ITEMS.register(bus);
        ModTabs.TABS.register(bus);
    }
}
