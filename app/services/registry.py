from __future__ import annotations

import random
import zlib
from collections import Counter

from app.storage import Sighting, Storage, Vehicle, normalize_plate

PROVINCES = (
    "Adana", "Adıyaman", "Afyonkarahisar", "Ağrı", "Amasya", "Ankara", "Antalya", "Artvin", "Aydın", "Balıkesir",
    "Bilecik", "Bingöl", "Bitlis", "Bolu", "Burdur", "Bursa", "Çanakkale", "Çankırı", "Çorum", "Denizli",
    "Diyarbakır", "Edirne", "Elazığ", "Erzincan", "Erzurum", "Eskişehir", "Gaziantep", "Giresun", "Gümüşhane",
    "Hakkari", "Hatay", "Isparta", "Mersin", "İstanbul", "İzmir", "Kars", "Kastamonu", "Kayseri", "Kırklareli",
    "Kırşehir", "Kocaeli", "Konya", "Kütahya", "Malatya", "Manisa", "Kahramanmaraş", "Mardin", "Muğla", "Muş",
    "Nevşehir", "Niğde", "Ordu", "Rize", "Sakarya", "Samsun", "Siirt", "Sinop", "Sivas", "Tekirdağ", "Tokat",
    "Trabzon", "Tunceli", "Şanlıurfa", "Uşak", "Van", "Yozgat", "Zonguldak", "Aksaray", "Bayburt", "Karaman",
    "Kırıkkale", "Batman", "Şırnak", "Bartın", "Ardahan", "Iğdır", "Yalova", "Karabük", "Kilis", "Osmaniye",
    "Düzce",
)


def province_of(plate: str | None) -> str | None:
    plate = normalize_plate(plate) or ""
    if len(plate) >= 2 and plate[:2].isdigit() and 1 <= int(plate[:2]) <= 81:
        return PROVINCES[int(plate[:2]) - 1]
    return None


class RegistryService:
    def __init__(self, storage: Storage):
        self.storage = storage
        from faker import Faker
        self.faker = Faker("tr_TR")

    def mock_owner(self, plate: str) -> tuple[str, str]:
        seed = zlib.crc32(plate.encode())
        self.faker.seed_instance(seed)
        rnd = random.Random(seed)
        phone = f"0555 {rnd.randint(100, 999)} {rnd.randint(10, 99)} {rnd.randint(10, 99)}"   # 0555: fictional
        return self.faker.name(), phone

    def observed(self, plate: str) -> tuple[str | None, str | None]:
        sightings = self.storage.sightings.by_plate(plate)
        colors = Counter(s.color for s in sightings if s.color)
        types = Counter(s.vehicle_type for s in sightings if s.vehicle_type)
        return (colors.most_common(1)[0][0] if colors else None,
                types.most_common(1)[0][0] if types else None)

    def ensure(self, plate: str | None) -> Vehicle | None:
        plate = normalize_plate(plate)
        if not plate:
            return None
        color, vtype = self.observed(plate)
        v = self.storage.vehicles.get(plate)
        if v is None:
            name, phone = self.mock_owner(plate)
            v = Vehicle(plate, owner_name=name, owner_city=province_of(plate) or "foreign",
                        owner_phone=phone, color=color, vehicle_type=vtype)
            v = self.storage.vehicles.save(v)
            self.storage.events.log("registry", f"profile created for {plate} (mock owner)", plate=plate)
            return v
        if (color and not v.color) or (vtype and not v.vehicle_type):
            v.color = v.color or color
            v.vehicle_type = v.vehicle_type or vtype
            v = self.storage.vehicles.save(v)
        return v

    def sync_all(self) -> int:
        before = self.storage.vehicles.count()
        for plate in self.storage.sightings.plate_stats():
            self.ensure(plate)
        return self.storage.vehicles.count() - before

    def backfill_colors(self, crops) -> int:
        from app.services.color import ColorClassifier
        classifier, done = ColorClassifier(), 0
        rows = self.storage.db.conn.execute(
            "SELECT id, vehicle_crop FROM sightings WHERE color IS NULL AND vehicle_crop IS NOT NULL").fetchall()
        for sid, rel in rows:
            color = classifier.classify(crops.load(rel))
            if color:
                self.storage.sightings.set_color(sid, color)
                done += 1
        return done

    def after_decision(self, s: Sighting) -> None:
        if s.final_plate:
            self.ensure(s.final_plate)
