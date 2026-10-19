package com.qwerty.model.registry;

import com.qwerty.model.QwertysModel;
import net.minecraft.world.item.BlockItem;
import net.minecraft.world.item.Item;
import net.minecraftforge.registries.DeferredRegister;
import net.minecraftforge.registries.ForgeRegistries;
import net.minecraftforge.registries.RegistryObject;

public final class ModItems {
    public static final DeferredRegister<Item> ITEMS =
            DeferredRegister.create(ForgeRegistries.ITEMS, QwertysModel.MODID);

    public static final RegistryObject<Item> HT100_DOOR_CAMERA = ITEMS.register("ht100_door_camera",
            () -> new BlockItem(ModBlocks.HT100_DOOR_CAMERA.get(), new Item.Properties()));

    public static final RegistryObject<Item> HT100_DOOR_CAMERA_AGED = ITEMS.register("ht100_door_camera_aged",
            () -> new BlockItem(ModBlocks.HT100_DOOR_CAMERA_AGED.get(), new Item.Properties()));

    private ModItems() {}
}
